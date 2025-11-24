use crate::config::{Config, Backend};
use crate::static_files::StaticFileHandler;
use anyhow::Result;
use bytes::Bytes;
use http_body_util::Full;
use hyper::server::conn::http1;
use hyper::service::service_fn;
use hyper::{Request, Response, StatusCode, body::Incoming};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::net::TcpListener;
use tracing::{info, error};

pub struct Server {
    config: Arc<Config>,
    static_handler: Arc<StaticFileHandler>,
}

pub struct ConnectionHandler;

impl Server {
    pub async fn new(config: Config) -> Result<Self> {
        let static_handler = Arc::new(StaticFileHandler::new(
            config.static_dir.clone().unwrap_or_else(|| PathBuf::from(".")),
        )?);

        Ok(Server {
            config: Arc::new(config),
            static_handler,
        })
    }

    pub async fn run(self) -> Result<()> {
        let addr: SocketAddr = self.config.bind_addr.parse()?;
        let listener = TcpListener::bind(addr).await?;
        
        info!("FLUX listening on {}", addr);
        info!("Static directory: {:?}", self.config.static_dir);

        loop {
            match listener.accept().await {
                Ok((stream, peer_addr)) => {
                    let config = self.config.clone();
                    let static_handler = self.static_handler.clone();
                    
                    tokio::spawn(async move {
                        let builder = hyper_util::server::conn::auto::Builder::new(hyper_util::rt::TokioExecutor::new());
                        
                        if let Err(e) = builder
                            .serve_connection(
                                hyper_util::rt::TokioIo::new(stream),
                                service_fn(move |req| {
                                    Self::handle_request(
                                        req,
                                        config.clone(),
                                        static_handler.clone(),
                                    )
                                }),
                            )
                            .await
                        {
                            error!("Connection error from {}: {}", peer_addr, e);
                        }
                    });
                }
                Err(e) => {
                    error!("Accept error: {}", e);
                }
            }
        }
    }

    async fn handle_request(
        req: Request<Incoming>,
        config: Arc<Config>,
        static_handler: Arc<StaticFileHandler>,
    ) -> Result<Response<Full<Bytes>>, hyper::Error> {
        let path = req.uri().path();
        
        match static_handler.serve(path).await {
            Ok(response) => Ok(response),
            Err(_) => {
                Ok(Response::builder()
                    .status(hyper::StatusCode::NOT_FOUND)
                    .body(Full::new(Bytes::from("Not Found")))
                    .unwrap())
            }
        }
    }
}
