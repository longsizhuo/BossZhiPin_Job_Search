## Main Content
This is a completely free script — all you need to do is configure your own OpenAI API.

If you find this script helpful during this tough job-hunting season, I would be truly honored if you could give it a **star** ⭐️.

If this script brings you some warmth in this cold recruitment season, that alone would mean a lot to me.

Please don’t use this script to exploit others. If someone is already at the point of relying on scripts to apply for jobs, they probably don’t have much left to be squeezed.

---

## Steps to Use

1. First, configure your OpenAI API (using a `.env` file or set it directly in the code).
2. Upload your PDF resume to the `auto_job_find` folder and name it **"my_cover.pdf"**.
3. Install all required packages.
4. Run `write_response.py`.

---

## About the Assistant

The script will automatically create an OpenAI Assistant and generate a local `.json` file. This file is only created on the first run. On subsequent runs, the existing Assistant will be reused if the JSON file is detected.

---

## Required Packages

- `python-dotenv`  
- `openai`  
- `selenium`  
- `robotframework`  
- `robotframework-seleniumlibrary`  
- `robotframework-pythonlibcore`  

---

## About RPA

Tutorial video on how to get started with [RPA](https://www.youtube.com/watch?v=65OPFmEgCbM&list=PLx4LEkEdFArgrdD_lvXe_hYBy8zM0Sp3b&index=1)

Recommended Plugin: Intellibot@Selenium Library

---

### 📺 Simple Tutorial Videos

- [Bilibili](https://www.bilibili.com/video/BV1UC4y1N78v/?share_source=copy_web&vd_source=b2608434484091fcc64d4eb85233122d)
- [YouTube](https://youtu.be/TlnytEi2lD8?si=jfcDj2MZqBptziZc)

---

## How to Run

Clone the project locally, then run the following in the root directory:
```bash
pip install -r requirements.txt
```

### Run with Assistant Mode

1. Open the `.env` file and configure your OpenAI API key.
2. Upload your resume PDF to the `auto_job_find` folder, named `my_cover.pdf`.
3. Run `write_response.py`.

Note: This mode does not support custom APIs but runs faster.

### Run with Langchain Mode

1. Again, configure your OpenAI API key and your custom API endpoint in the `.env` file.
2. Put your resume in the `resume` folder.
3. Run `write_response.py`.

### Run with ChatGPT-4 and Above

If you're using newer ChatGPT models, you may encounter an error if you're not using version `v1.1.1`:

```
Error code: 400 - {'error': {'message': "The requested model 'gpt-4o-mini' cannot be used with the Assistants API in v1. Follow the migration guide to upgrade to v2: https://platform.openai.com/docs/assistants/migration."}}
```

#### Solution:
1. Upgrade OpenAI package:
```shell
pip install --upgrade openai
```
2. Modify the `create_assistant` function structure. See the [migration guide](https://platform.openai.com/docs/assistants/migration) for details.

> Alternatively, manually create an assistant on the [OpenAI Platform](https://platform.openai.com/assistants/), then copy its code into your `assistant.json` file:
```json
{"assistant_id": "asst_token"}
```

---

## Alternative JavaScript Version

Some kind contributors have built easier-to-use versions based on JavaScript. Although these versions may not support Assistant-based retrieval and may require manual preprocessing of resumes, they are still very helpful.

GitHub link:  
[https://github.com/noBaldAaa/find-job](https://github.com/noBaldAaa/find-job)

---

## Azure-based Version

An alternative version using Azure's OpenAI API is available here:
[https://github.com/LouisCaixuran/auto_job_find_azure](https://github.com/LouisCaixuran/auto_job_find_azure)



## 正文
这是一个完全免费的脚本，只需要你们自己配置好openai的api即可

希望您能给我点个 **star**

如果在这个寒冷的招聘季，这个脚本能给您一些帮助，带来一些温暖，将让我非常荣幸

希望不要有人拿着我的脚本去割韭菜，都已经被逼到用这种脚本投简历的地步了，身上也没啥油水可榨了吧。

## 操作步骤

1. 请首先配置好 openai 的 api（使用.env文件或者在代码中配置）
2. 将pdf简历上传到文件夹 auto_job_find 里，命名为 **“my_cover.pdf"**
3. 将需要的包安装好
4. 执行 write_response.py

## 关于 asistant

会自动生成 openai 的 asistant，并在本地产生一个 .json 文件，只有第一次运行的时候才会产生，后面每次运行如果检测到这个 json ，就会调用已有的 asistant。

## 使用到的包

- `python-dotenv`
- `openai`
- `selenium`
- `robotframework`
- `robotframework-seleniumlibrary`
- `robotframework-pythonlibcore`
- `faiss-cpu不支持3.12（faiss-gpu不清楚）。建议大家用3.11及以下版本的python运行脚本。` from @[huanmit](https://github.com/huanmit)

## About RPA

tutorial video about how to learn [rpa](https://www.youtube.com/watch?v=65OPFmEgCbM&list=PLx4LEkEdFArgrdD_lvXe_hYBy8zM0Sp3b&index=1)

Plugin: Intellibot@Selenium Library

------------------下面是简单的教学视频---------------------

[B站链接](https://www.bilibili.com/video/BV1UC4y1N78v/?share_source=copy_web&vd_source=b2608434484091fcc64d4eb85233122d)

[油管链接](https://youtu.be/TlnytEi2lD8?si=jfcDj2MZqBptziZc)

## 运行方式
先将该项目clone到本地，然后在项目根目录下执行
```bash
pip install -r requirements.txt
```

### assistant方式运行
打开.env文件，在里面配置好OpenAI的API key
随后将pdf简历上传到文件夹auto_job_find里，命名为“my_cover".随后执行write_response.py即可
这种方式不支持使用自定义api，优势是执行速度更快
如果需要使用自定义api，请使用下面的方式运行

### langchain方式
同样打开.env文件，在里面配置好OpenAI的API key和你想要请求的api地址
随后将pdf简历放到文件夹resume里
最后执行write_response.py即可


### chatgpt4 及以上运行方式
如果尝试使用更新的chatGPT则不能保持最新版本为`v1.1.1`，同时如果报错信息为`An error occurred: Error code: 400 - {'error': {'message': "The requested model 'gpt-4o-mini' cannot be used with the Assistants API in v1. Follow the migration guide to upgrade to v2: https://platform.openai.com/docs/assistants/migration.", 'type': 'invalid_request_error', 'param': 'model', 'code': 'unsupported_model'}}`

1. 需要手动将chatgpt更新到最新版，

```shell
pip install --upgrade openai
```

2. 以及更改`create_assistant`中的结构体，详细参考[迁移模型](https://platform.openai.com/docs/assistants/migration)中的描述。建议直接在[平台](https://platform.openai.com/assistants/)上手动添加最新的assist然后复制代码到`assistant.json`中最为方便.
```json
{"assistant_id": "asst_token"}
```


------------下面是其他朋友基于js构建的更加易于使用的代码---------------

我一直也在考虑如何可以降低各位的使用门槛，基于现在项目的热度，我发现很多朋友都需要这个东西来帮助自己，但是我相信对于更多的人而言，甚至vpn都是一个障碍

下面这位朋友基于js实现了一个更加简易的版本，虽然因为调用的免费api，无法使用assistant进行retrival，需要自己对简历进行简单的处理，但我依然认为这是个很棒的项目

感谢朋友的贡献，以下是链接：

[https://github.com/noBaldAaa](https://github.com/noBaldAaa/find-job)https://github.com/noBaldAaa/find-job

------------下面是其他朋友基于azure的openai api构建的版本的更加易于使用的代码---------------
https://github.com/LouisCaixuran/auto_job_find_azure


