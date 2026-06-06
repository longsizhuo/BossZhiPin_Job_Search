// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{convert::Infallible, error::Error, path::PathBuf};

use pyo3::wrap_pymodule;
use pytauri::standalone::{
    dunce::simplified, PythonInterpreterBuilder, PythonInterpreterEnv, PythonScript,
};
use tauri::utils::platform::resource_dir;

use boss_zhipin_lib::{ext_mod, tauri_generate_context};

fn main() -> Result<Infallible, Box<dyn Error>> {
    // 告诉 boss_zhipin.tauri 用 standalone 分支（用 pytauri 而非 pytauri-wheel）
    std::env::set_var("BOSS_TAURI_STANDALONE", "1");

    let py_env = if cfg!(dev) {
        // `tauri dev` 模式——用 repo 里的 .venv 跑 Python
        // {repo_root}/src-tauri 往上两级到 repo root
        let mut venv_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        venv_dir.pop(); // -> {repo_root}
        venv_dir.push(".venv");
        assert!(
            venv_dir.is_dir(),
            "Python virtual environment not found at: {}",
            venv_dir.display()
        );
        PythonInterpreterEnv::Venv(venv_dir.into())
    } else {
        // Release / bundle 模式——用打包进 .app 的 embedded Python
        let context = tauri_generate_context();
        let resource_dir = resource_dir(context.package_info(), &tauri::Env::default())
            .map_err(|err| format!("failed to get resource dir: {err}"))?;
        // 去掉 Windows UNC 前缀 \\?\，Python 那边不认
        let resource_dir = simplified(&resource_dir).to_owned();
        PythonInterpreterEnv::Standalone(resource_dir.into())
    };

    // 等价于 `python -m boss_zhipin.tauri` —— 跑 boss_zhipin/tauri/__main__.py
    let py_script = PythonScript::Module("boss_zhipin.tauri".into());

    // 把 ext_mod 在内存里注册给 pytauri 运行时（不需要单独编译成 .so/.dylib）
    let builder =
        PythonInterpreterBuilder::new(py_env, py_script, |py| wrap_pymodule!(ext_mod)(py));
    let interpreter = builder.build()?;

    let exit_code = interpreter.run();
    std::process::exit(exit_code);
}
