const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const { spawn, exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

let mainWindow;
let pythonProcess = null;
let jobServiceClient = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer/index.html'));
}

async function killProcessOnPort(port) {
  try {
    // 在 Windows 上查找占用端口的进程
    const { stdout } = await execPromise(`netstat -ano | findstr :${port}`);
    if (stdout) {
      // 提取 PID
      const match = stdout.match(/\s+(\d+)$/);
      if (match) {
        const pid = match[1];
        console.log(`Found process ${pid} using port ${port}`);
        // 终止进程
        await execPromise(`taskkill /F /PID ${pid}`);
        console.log(`Successfully killed process ${pid}`);
      }
    }
  } catch (error) {
    // 如果端口没有被占用，netstat 会返回错误，这是正常的
    if (!error.message.includes('no connections')) {
      console.error('Error checking port:', error);
    }
  }
}

async function startPythonServer() {
  try {
    // 先检查并关闭占用 50051 端口的进程
    await killProcessOnPort(50051);
    
    // 等待一小段时间确保端口完全释放
    await new Promise(resolve => setTimeout(resolve, 1000));

    // 使用 python 命令启动服务器
    pythonProcess = spawn('python', ['../python/grpc_server.py'], {
      stdio: ['inherit', 'pipe', 'pipe']
    });

    if (!pythonProcess) {
      throw new Error('Failed to start Python process');
    }

    if (pythonProcess.stdout) {
      pythonProcess.stdout.on('data', (data) => {
        console.log(`Python server: ${data}`);
        if (data.toString().includes('gRPC server started')) {
          setupGrpcClient();
        }
      });
    }

    if (pythonProcess.stderr) {
      pythonProcess.stderr.on('data', (data) => {
        console.error(`Python server error: ${data}`);
      });
    }

    pythonProcess.on('error', (error) => {
      console.error('Failed to start Python process:', error);
    });

  } catch (error) {
    console.error('Error in startPythonServer:', error);
    throw error;
  }
}

function setupGrpcClient() {
  const PROTO_PATH = path.join(__dirname, '../../python/proto/job_service.proto');
  const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
  });

  const jobService = grpc.loadPackageDefinition(packageDefinition).job_service;
  jobServiceClient = new jobService.JobService(
    'localhost:50051',
    grpc.credentials.createInsecure()
  );

  // 测试连接
  jobServiceClient.TestConnection({}, (err, response) => {
    if (err) {
      console.error('Failed to connect to Python server:', err);
      mainWindow.webContents.send('server-error', 'Failed to connect to Python server');
    } else {
      console.log('Successfully connected to Python server');
      mainWindow.webContents.send('server-ready');
    }
  });
}

// Initialize the application
async function initializeApp() {
  try {
    await startPythonServer();
    await setupGrpcClient();
    createWindow();
  } catch (error) {
    console.error('Failed to initialize application:', error);
    app.quit();
  }
}

app.whenReady().then(initializeApp);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

// IPC 事件处理
ipcMain.handle('upload-resume', async (event, fileContent, fileName) => {
  if (!jobServiceClient) {
    throw new Error('Job service client not initialized');
  }
  
  return new Promise((resolve, reject) => {
    jobServiceClient.UploadResume({ file_content: fileContent, file_name: fileName }, (err, response) => {
      if (err) reject(err);
      else resolve(response);
    });
  });
});

ipcMain.handle('set-api-key', async (event, apiKey, baseUrl) => {
  return new Promise((resolve, reject) => {
    jobServiceClient.SetApiKey({ api_key: apiKey, base_url: baseUrl }, (err, response) => {
      if (err) reject(err);
      else resolve(response);
    });
  });
});

ipcMain.handle('start-job', async (event, jobConfig) => {
  if (!jobServiceClient) {
    throw new Error('gRPC client not initialized');
  }

  // 在这里才开始执行主要业务逻辑
  const stream = jobServiceClient.StartJob({
    url: jobConfig.url,
    browser_type: jobConfig.browserType,
    job_type: jobConfig.jobType
  });

  stream.on('data', (status) => {
    mainWindow.webContents.send('job-status', status);
  });

  stream.on('error', (error) => {
    mainWindow.webContents.send('job-error', error.message);
  });

  stream.on('end', () => {
    mainWindow.webContents.send('job-completed');
  });
});

ipcMain.handle('stop-job', async () => {
  return new Promise((resolve, reject) => {
    jobServiceClient.StopJob({}, (err, response) => {
      if (err) reject(err);
      else resolve(response);
    });
  });
}); 