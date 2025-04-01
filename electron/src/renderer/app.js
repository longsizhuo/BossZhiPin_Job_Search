const { ipcRenderer } = require('electron');

// DOM 元素
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadStatus = document.getElementById('uploadStatus');
const apiKeyInput = document.getElementById('apiKey');
const baseUrlInput = document.getElementById('baseUrl');
const saveApiKeyBtn = document.getElementById('saveApiKey');
const jobTypeInput = document.getElementById('jobType');
const browserTypeSelect = document.getElementById('browserType');
const startJobBtn = document.getElementById('startJob');
const stopJobBtn = document.getElementById('stopJob');
const statusArea = document.getElementById('status');
const progressBar = document.getElementById('progress');

// 文件拖放处理
dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  e.stopPropagation();
  dropZone.style.borderColor = '#2c3e50';
});

dropZone.addEventListener('dragleave', (e) => {
  e.preventDefault();
  e.stopPropagation();
  dropZone.style.borderColor = '#ccc';
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  e.stopPropagation();
  dropZone.style.borderColor = '#ccc';
  
  const file = e.dataTransfer.files[0];
  if (file && file.type === 'application/pdf') {
    handleFileUpload(file);
  } else {
    uploadStatus.textContent = '请上传 PDF 格式的简历文件';
  }
});

dropZone.addEventListener('click', () => {
  fileInput.click();
});

fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) {
    handleFileUpload(file);
  }
});

async function handleFileUpload(file) {
  uploadStatus.textContent = '正在上传简历...';
  try {
    const buffer = await file.arrayBuffer();
    await ipcRenderer.invoke('upload-resume', new Uint8Array(buffer));
    uploadStatus.textContent = '简历上传成功！';
  } catch (error) {
    uploadStatus.textContent = `上传失败: ${error.message}`;
  }
}

// API Key 配置
saveApiKeyBtn.addEventListener('click', async () => {
  const apiKey = apiKeyInput.value.trim();
  const baseUrl = baseUrlInput.value.trim();
  
  if (!apiKey) {
    alert('请输入 OpenAI API Key');
    return;
  }
  
  try {
    await ipcRenderer.invoke('set-api-key', { apiKey, baseUrl });
    alert('配置保存成功！');
  } catch (error) {
    alert(`配置保存失败: ${error.message}`);
  }
});

// 任务控制
startJobBtn.addEventListener('click', async () => {
  const jobType = jobTypeInput.value.trim();
  const browserType = browserTypeSelect.value;
  
  if (!jobType) {
    alert('请输入职位类型');
    return;
  }
  
  try {
    startJobBtn.disabled = true;
    stopJobBtn.disabled = false;
    statusArea.textContent = '正在启动任务...';
    progressBar.style.width = '0%';
    
    await ipcRenderer.invoke('start-job', { jobType, browserType });
  } catch (error) {
    statusArea.textContent = `任务启动失败: ${error.message}`;
    startJobBtn.disabled = false;
    stopJobBtn.disabled = true;
  }
});

stopJobBtn.addEventListener('click', async () => {
  try {
    await ipcRenderer.invoke('stop-job');
    statusArea.textContent = '任务已停止';
    startJobBtn.disabled = false;
    stopJobBtn.disabled = true;
    progressBar.style.width = '0%';
  } catch (error) {
    alert(`停止任务失败: ${error.message}`);
  }
});

// 监听任务状态更新
ipcRenderer.on('job-status', (event, data) => {
  statusArea.textContent = data.message;
  if (data.progress !== undefined) {
    progressBar.style.width = `${data.progress}%`;
  }
});

ipcRenderer.on('job-error', (event, error) => {
  statusArea.textContent = `错误: ${error}`;
  startJobBtn.disabled = false;
  stopJobBtn.disabled = true;
  progressBar.style.width = '0%';
});

ipcRenderer.on('job-complete', () => {
  statusArea.textContent = '任务完成！';
  startJobBtn.disabled = false;
  stopJobBtn.disabled = true;
  progressBar.style.width = '100%';
}); 