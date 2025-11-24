use anyhow::Result;
use wasmtime::{Engine, Linker, Module, Store};
use tracing::info;

pub struct WasmRuntime {
    engine: Engine,
}

impl WasmRuntime {
    pub fn new() -> Result<Self> {
        let engine = Engine::default();
        Ok(Self { engine })
    }

    pub fn run_example(&self) -> Result<()> {
        let mut store = Store::new(&self.engine, ());
        let module = Module::new(&self.engine, r#"(module (func (export "run") (result i32) i32.const 42))"#)?;
        let linker = Linker::new(&self.engine);
        let instance = linker.instantiate(&mut store, &module)?;
        let run = instance.get_typed_func::<(), i32>(&mut store, "run")?;
        let result = run.call(&mut store, ())?;
        
        info!("Wasm execution result: {}", result);
        Ok(())
    }
}
