## Main Content
This is a completely free script — all you need to do is configure your own OpenAI API.

If you find this script helpful during this tough job-hunting season, I would be truly honored if you could give it a **star** ⭐️.

If this script brings you some warmth in this cold recruitment season, that alone would mean a lot to me.

Please don’t use this script to exploit others. If someone is already at the point of relying on scripts to apply for jobs, they probably don’t have much left to be squeezed.


[中文文档](README_CN.md) 

[English](README.md)

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



