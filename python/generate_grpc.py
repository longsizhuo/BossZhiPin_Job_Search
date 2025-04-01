import os
import subprocess

def generate_grpc_code():
    # 确保 proto 目录存在
    os.makedirs('proto', exist_ok=True)
    
    # 生成 Python 代码
    subprocess.run([
        'python', '-m', 'grpc_tools.protoc',
        '-I./proto',
        '--python_out=.',
        '--grpc_python_out=.',
        './proto/job_service.proto'
    ])
    
    print("gRPC 代码生成完成")

if __name__ == '__main__':
    generate_grpc_code() 