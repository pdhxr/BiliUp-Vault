use std::{
    fs,
    io::{Read, Write},
    net::{Ipv4Addr, SocketAddrV4, TcpStream},
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use tauri::{Manager, RunEvent, Url, WindowEvent};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

const DEFAULT_PORT: u16 = 8765;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(20);

struct SidecarState(Mutex<Option<CommandChild>>);
struct CurrentPortState(Mutex<Option<u16>>);
struct ShutdownState(AtomicBool);

fn data_directory() -> Result<PathBuf, String> {
    dirs::data_local_dir()
        .map(|path| path.join("BiliUp"))
        .ok_or_else(|| "无法定位 BiliUp 应用配置目录".to_string())
}

fn configured_port(config_path: &Path) -> Result<u16, String> {
    if !config_path.is_file() {
        return Ok(DEFAULT_PORT);
    }
    let text =
        fs::read_to_string(config_path).map_err(|error| format!("无法读取配置文件：{error}"))?;
    let data: serde_json::Value =
        serde_json::from_str(&text).map_err(|error| format!("配置文件不是有效 JSON：{error}"))?;
    let object = data
        .as_object()
        .ok_or_else(|| "配置文件根节点必须是对象".to_string())?;
    let Some(value) = object.get("desktop_port") else {
        return Ok(DEFAULT_PORT);
    };
    let port = value
        .as_u64()
        .ok_or_else(|| "desktop_port 必须是整数".to_string())?;
    if !(1024..=65535).contains(&port) {
        return Err("desktop_port 必须在 1024–65535 之间".to_string());
    }
    Ok(port as u16)
}

fn health_is_biliup(port: u16, expected_instance: &str) -> bool {
    let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, port);
    let Ok(mut stream) = TcpStream::connect_timeout(&address.into(), Duration::from_millis(250))
    else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let request =
        format!("GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    let Some(body) = response.split("\r\n\r\n").nth(1) else {
        return false;
    };
    serde_json::from_str::<serde_json::Value>(body)
        .ok()
        .is_some_and(|data| {
            data.get("app") == Some(&serde_json::Value::String("biliup".into()))
                && data.get("status") == Some(&serde_json::Value::String("ok".into()))
                && data.get("instance")
                    == Some(&serde_json::Value::String(expected_instance.into()))
        })
}

fn startup_error_message(output: &str) -> Option<String> {
    output.lines().find_map(|line| {
        line.trim()
            .strip_prefix("BILIUP_STARTUP_ERROR:")
            .map(str::trim)
            .filter(|message| !message.is_empty())
            .map(str::to_string)
    })
}

fn show_error(window: &tauri::WebviewWindow, message: &str, config_path: &Path) {
    let message = serde_json::to_string(message).unwrap_or_else(|_| "\"BiliUp 启动失败\"".into());
    let path =
        serde_json::to_string(&config_path.display().to_string()).unwrap_or_else(|_| "\"\"".into());
    let _ = window.eval(format!("window.showError({message}, {path});"));
}

fn stop_sidecar(app: &tauri::AppHandle) {
    let state = app.state::<SidecarState>();
    if let Ok(mut child) = state.0.lock() {
        if let Some(child) = child.take() {
            let _ = child.kill();
        }
    };
}

fn request_backend_shutdown(port: u16) {
    let address = SocketAddrV4::new(Ipv4Addr::LOCALHOST, port);
    let Ok(mut stream) = TcpStream::connect_timeout(&address.into(), Duration::from_millis(300))
    else {
        return;
    };
    let request = format!(
        "POST /api/desktop/shutdown HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-BiliUp-Client: desktop\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    );
    let _ = stream.write_all(request.as_bytes());
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let mut response = [0_u8; 256];
    let _ = stream.read(&mut response);
}

fn begin_shutdown(app: tauri::AppHandle, port: u16) {
    let shutdown = app.state::<ShutdownState>();
    if shutdown.0.swap(true, Ordering::SeqCst) {
        return;
    }
    thread::spawn(move || {
        request_backend_shutdown(port);
        thread::sleep(Duration::from_millis(900));
        stop_sidecar(&app);
        app.exit(0);
    });
}

fn start_backend(app: tauri::AppHandle) -> Result<u16, String> {
    let data_dir = data_directory()?;
    fs::create_dir_all(&data_dir).map_err(|error| format!("无法创建应用配置目录：{error}"))?;
    let config_path = data_dir.join("config.json");
    let port = configured_port(&config_path)?;

    let port_text = port.to_string();
    let data_dir_text = data_dir.to_string_lossy().to_string();
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let instance_token = format!("{}-{nonce}", std::process::id());
    let command = app
        .shell()
        .sidecar("biliup-backend")
        .map_err(|error| format!("无法准备 Python 后端：{error}"))?
        .args([
            "--port",
            &port_text,
            "--data-dir",
            &data_dir_text,
            "--instance-token",
            &instance_token,
        ]);
    let (mut events, child) = command
        .spawn()
        .map_err(|error| format!("无法启动 Python 后端：{error}"))?;
    app.state::<SidecarState>()
        .0
        .lock()
        .map_err(|_| "无法保存 Python 后端进程状态".to_string())?
        .replace(child);
    app.state::<CurrentPortState>()
        .0
        .lock()
        .map_err(|_| "无法保存本次桌面端口".to_string())?
        .replace(port);

    let terminated = Arc::new(AtomicBool::new(false));
    let event_terminated = Arc::clone(&terminated);
    let startup_error = Arc::new(Mutex::new(None::<String>));
    let event_startup_error = Arc::clone(&startup_error);
    tauri::async_runtime::spawn(async move {
        use tauri_plugin_shell::process::CommandEvent;
        let mut ended = false;
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stderr(bytes) => {
                    let output = String::from_utf8_lossy(&bytes);
                    if let Some(message) = startup_error_message(&output) {
                        if let Ok(mut error) = event_startup_error.lock() {
                            error.replace(message);
                        }
                    }
                }
                CommandEvent::Error(message) => {
                    if let Ok(mut error) = event_startup_error.lock() {
                        error.replace(message);
                    }
                    ended = true;
                }
                CommandEvent::Terminated(_) => {
                    ended = true;
                }
                _ => {}
            }
        }
        if ended {
            event_terminated.store(true, Ordering::SeqCst);
        }
    });

    let deadline = Instant::now() + STARTUP_TIMEOUT;
    while Instant::now() < deadline {
        if terminated.load(Ordering::SeqCst) {
            stop_sidecar(&app);
            let message = startup_error
                .lock()
                .ok()
                .and_then(|error| error.clone())
                .unwrap_or_else(|| "Python 后端在完成启动前退出".to_string());
            return Err(message);
        }
        if health_is_biliup(port, &instance_token) {
            return Ok(port);
        }
        thread::sleep(Duration::from_millis(200));
    }
    stop_sidecar(&app);
    Err(format!("等待 BiliUp 后端启动超时（端口 {port}）"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState(Mutex::new(None)))
        .manage(CurrentPortState(Mutex::new(None)))
        .manage(ShutdownState(AtomicBool::new(false)));

    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }));
    }

    let app = builder
        .setup(|app| {
            let handle = app.handle().clone();
            let window = app
                .get_webview_window("main")
                .ok_or("找不到 BiliUp 主窗口")?;
            thread::spawn(move || {
                let config_path = data_directory()
                    .unwrap_or_else(|_| PathBuf::from("BiliUp"))
                    .join("config.json");
                match start_backend(handle.clone()) {
                    Ok(port) => {
                        if let Ok(url) = Url::parse(&format!("http://127.0.0.1:{port}/")) {
                            let _ = window.navigate(url);
                        }
                    }
                    Err(error) => show_error(&window, &error, &config_path),
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let port = window
                    .app_handle()
                    .state::<CurrentPortState>()
                    .0
                    .lock()
                    .ok()
                    .and_then(|port| *port)
                    .unwrap_or(DEFAULT_PORT);
                begin_shutdown(window.app_handle().clone(), port);
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building BiliUp desktop application");

    app.run(|app, event| match event {
        RunEvent::ExitRequested { api, .. }
            if !app.state::<ShutdownState>().0.load(Ordering::SeqCst) =>
        {
            api.prevent_exit();
            let port = app
                .state::<CurrentPortState>()
                .0
                .lock()
                .ok()
                .and_then(|port| *port)
                .unwrap_or(DEFAULT_PORT);
            begin_shutdown(app.clone(), port);
        }
        RunEvent::Exit => {
            let port = app
                .state::<CurrentPortState>()
                .0
                .lock()
                .ok()
                .and_then(|port| *port)
                .unwrap_or(DEFAULT_PORT);
            request_backend_shutdown(port);
            thread::sleep(Duration::from_millis(900));
            stop_sidecar(app);
        }
        _ => {}
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_config_uses_default_port() {
        let path = std::env::temp_dir().join("biliup-missing-config.json");
        assert_eq!(configured_port(&path).unwrap(), DEFAULT_PORT);
    }

    #[test]
    fn port_validation_rejects_wrong_json_types_and_ranges() {
        let root = std::env::temp_dir().join(format!("biliup-rust-test-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let path = root.join("config.json");
        for content in [
            r#"{"desktop_port":true}"#,
            r#"{"desktop_port":"8765"}"#,
            r#"{"desktop_port":1023}"#,
            r#"{"desktop_port":65536}"#,
        ] {
            fs::write(&path, content).unwrap();
            assert!(configured_port(&path).is_err());
        }
    }

    #[test]
    fn startup_error_extracts_safe_sidecar_message() {
        let output = "log line\nBILIUP_STARTUP_ERROR:端口 8765 已被 Safari（PID 42）占用\n";
        assert_eq!(
            startup_error_message(output).as_deref(),
            Some("端口 8765 已被 Safari（PID 42）占用")
        );
        assert_eq!(startup_error_message("ordinary stderr"), None);
    }
}
