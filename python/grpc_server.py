import grpc
from concurrent import futures
import os
import time
from typing import Iterator
import job_service_pb2
import job_service_pb2_grpc
from write_response import send_job_descriptions_to_chat
import threading
import queue
import appdirs
import logging

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("job_service.log"),
                              logging.StreamHandler()])

class JobServiceServicer(job_service_pb2_grpc.JobServiceServicer):
    def __init__(self):
        self.api_key = None
        self.base_url = None
        self.resume_path = None
        self.is_running = False
        # 创建应用数据目录
        self.app_data_dir = appdirs.user_data_dir('BossZhiPin_Job_Search', 'BossZhiPin')
        self.resume_dir = os.path.join(self.app_data_dir, 'resume')
        logging.info(f"Resume directory: {self.resume_dir}")
        
        try:
            os.makedirs(self.resume_dir, exist_ok=True)
            logging.info(f"Created resume directory: {self.resume_dir}")
        except Exception as e:
            logging.error(f"Error creating resume directory: {e}")

    def TestConnection(self, request, context):
        """测试与服务器的连接"""
        return job_service_pb2.TestConnectionResponse(
            success=True,
            message="服务器连接正常"
        )

    def UploadResume(self, request, context):
        try:
            # 检查文件名是否为空，如果为空则使用默认文件名
            file_name = request.file_name
            if not file_name or file_name.strip() == '':
                file_name = f"resume_{int(time.time())}.pdf"
                logging.info(f"Empty filename received, using default: {file_name}")
            
            # 保存简历文件到应用数据目录
            file_path = os.path.join(self.resume_dir, file_name)
            logging.info(f"Saving resume to: {file_path}")
            logging.info(f"File content length: {len(request.file_content)} bytes")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(request.file_content)
            
            logging.info(f"Resume saved successfully at: {file_path}")
            
            # 检查文件是否成功保存
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                logging.info(f"File exists with size: {file_size} bytes")
            else:
                logging.error(f"File does not exist after save: {file_path}")
            
            self.resume_path = file_path
            
            # 尝试保存到额外的位置(桌面)，确保用户可以找到
            try:
                desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                desktop_resume_path = os.path.join(desktop_path, f"BossZhiPin_Resume_{file_name}")
                with open(desktop_resume_path, 'wb') as f:
                    f.write(request.file_content)
                logging.info(f"Resume also saved to desktop: {desktop_resume_path}")
                
                return job_service_pb2.UploadResumeResponse(
                    success=True,
                    message=f"简历已保存到: {file_path} 和 {desktop_resume_path}"
                )
            except Exception as e:
                logging.error(f"Error saving resume to desktop: {e}")
                
            return job_service_pb2.UploadResumeResponse(
                success=True,
                message=f"简历已保存到: {file_path}"
            )
        except Exception as e:
            logging.error(f"Error saving resume: {e}")
            return job_service_pb2.UploadResumeResponse(success=False, message=str(e))

    def SetApiKey(self, request, context):
        try:
            self.api_key = request.api_key
            self.base_url = request.base_url
            return job_service_pb2.SetApiKeyResponse(success=True)
        except Exception as e:
            return job_service_pb2.SetApiKeyResponse(success=False, message=str(e))

    def StartJob(self, request, context):
        if not all([self.api_key, self.resume_path]):
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, 
                        'API key and resume must be set before starting job')

        try:
            # 只在这里初始化 OpenAI 客户端
            os.environ['OPENAI_API_KEY'] = self.api_key
            if self.base_url:
                os.environ['OPENAI_BASE_URL'] = self.base_url

            # 开始执行主要业务逻辑
            yield job_service_pb2.JobStatus(
                status="running",
                message="Starting job processing..."
            )

            # 调用 write_response 的主要逻辑
            from write_response import process_job
            for status in process_job(
                url=request.url,
                browser_type=request.browser_type,
                job_type=request.job_type,
                resume_path=self.resume_path
            ):
                yield status

        except Exception as e:
            yield job_service_pb2.JobStatus(
                status="error",
                message=str(e)
            )

    def StopJob(self, request, context):
        if not self.is_running:
            return job_service_pb2.StopJobResponse(
                success=False,
                message="没有正在运行的任务",
                final_status="stopped"
            )

        try:
            self.is_running = False
            if self.current_thread:
                self.current_thread.join(timeout=5)
            
            return job_service_pb2.StopJobResponse(
                success=True,
                message="任务已停止",
                final_status="stopped"
            )
        except Exception as e:
            return job_service_pb2.StopJobResponse(
                success=False,
                message=f"停止任务失败: {str(e)}",
                final_status="error"
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    job_service_pb2_grpc.add_JobServiceServicer_to_server(JobServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("gRPC server started")  # 添加启动成功的标志
    server.wait_for_termination()

if __name__ == '__main__':
    serve() 