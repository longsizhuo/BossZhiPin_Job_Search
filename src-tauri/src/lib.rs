// PyO3 ext_mod 入口——standalone Rust binary 在内存里注册一个 `ext_mod`
// pymodule，里头通过 pymodule_export 把 builder_factory / context_factory
// 这俩 Python 端要用的工厂函数暴露给 pytauri 运行时。
//
// 没有自定义 Rust command——所有业务逻辑在 Python 端的
// `boss_zhipin.tauri` 包里，用 @commands.command 注册。
use pyo3::prelude::*;

pub fn tauri_generate_context() -> tauri::Context {
    tauri::generate_context!()
}

#[pymodule(gil_used = false)]
#[pyo3(name = "ext_mod")]
pub mod ext_mod {
    use super::*;

    #[pymodule_init]
    fn init(module: &Bound<'_, PyModule>) -> PyResult<()> {
        pytauri::pymodule_export(
            module,
            // context_factory 的 Python 端
            |_args, _kwargs| Ok(tauri_generate_context()),
            // builder_factory 的 Python 端——Python 命令在
            // commands.generate_handler(portal) 里挂上去，所以这里返回一个
            // 还没装 invoke_handler 的空 builder 就行
            |_args, _kwargs| Ok(tauri::Builder::default()),
        )
    }
}
