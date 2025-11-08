#ifndef WEB_UI_H
#define WEB_UI_H

const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DD-DRIVE 双电机控制</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 20px;
    }
    .container {
      background: white;
      border-radius: 20px;
      padding: 30px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
      max-width: 600px;
      width: 100%;
    }
    h1 {
      text-align: center;
      color: #333;
      margin-bottom: 10px;
      font-size: 28px;
    }
    .subtitle {
      text-align: center;
      color: #666;
      margin-bottom: 30px;
      font-size: 14px;
    }
    .motor-section {
      background: #f8f9fa;
      border-radius: 15px;
      padding: 20px;
      margin-bottom: 20px;
    }
    .motor-title {
      font-size: 18px;
      font-weight: bold;
      color: #495057;
      margin-bottom: 15px;
    }
    .slider-group {
      margin-bottom: 15px;
    }
    label {
      display: block;
      margin-bottom: 8px;
      color: #666;
      font-size: 14px;
    }
    input[type="range"] {
      width: 100%;
      height: 8px;
      border-radius: 5px;
      background: #ddd;
      outline: none;
      -webkit-appearance: none;
    }
    input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none;
      appearance: none;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #667eea;
      cursor: pointer;
    }
    input[type="range"]::-moz-range-thumb {
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #667eea;
      cursor: pointer;
      border: none;
    }
    .value-display {
      text-align: center;
      font-size: 24px;
      font-weight: bold;
      color: #667eea;
      margin-top: 10px;
    }
    .telemetry {
      display: flex;
      justify-content: space-between;
      margin-top: 10px;
      font-size: 12px;
      color: #888;
    }
    .btn-group {
      display: flex;
      gap: 10px;
      margin-top: 20px;
    }
    button {
      flex: 1;
      padding: 15px;
      border: none;
      border-radius: 10px;
      font-size: 16px;
      font-weight: bold;
      cursor: pointer;
      transition: all 0.3s;
    }
    .btn-send {
      background: #667eea;
      color: white;
    }
    .btn-send:hover {
      background: #5568d3;
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(102,126,234,0.4);
    }
    .btn-stop {
      background: #dc3545;
      color: white;
    }
    .btn-stop:hover {
      background: #c82333;
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(220,53,69,0.4);
    }
    .status {
      text-align: center;
      margin-top: 20px;
      padding: 10px;
      border-radius: 10px;
      font-size: 14px;
    }
    .status.success { background: #d4edda; color: #155724; }
    .status.error { background: #f8d7da; color: #721c24; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🚗 DD-DRIVE</h1>
    <div class="subtitle">双电机 PID 速度控制</div>
    
    <div class="motor-section">
      <div class="motor-title">⚙️ 左电机 (Motor L)</div>
      <div class="slider-group">
        <label for="sliderL">目标速度 (counts/s): -2000 ~ +2000</label>
        <input type="range" id="sliderL" min="-2000" max="2000" value="0" step="10">
        <div class="value-display" id="valueL">0</div>
        <div class="telemetry">
          <span>实际速度: <strong id="curL">--</strong></span>
        </div>
      </div>
    </div>

    <div class="motor-section">
      <div class="motor-title">⚙️ 右电机 (Motor R)</div>
      <div class="slider-group">
        <label for="sliderR">目标速度 (counts/s): -2000 ~ +2000</label>
        <input type="range" id="sliderR" min="-2000" max="2000" value="0" step="10">
        <div class="value-display" id="valueR">0</div>
        <div class="telemetry">
          <span>实际速度: <strong id="curR">--</strong></span>
        </div>
      </div>
    </div>

    <div class="btn-group">
      <button class="btn-send" onclick="sendCmd()">发送指令</button>
      <button class="btn-stop" onclick="stopMotors()">紧急停止</button>
    </div>

    <div class="status" id="status" style="display:none;"></div>
  </div>

  <script>
    const sliderL = document.getElementById('sliderL');
    const sliderR = document.getElementById('sliderR');
    const valueL = document.getElementById('valueL');
    const valueR = document.getElementById('valueR');
    const curL = document.getElementById('curL');
    const curR = document.getElementById('curR');
    const status = document.getElementById('status');

    sliderL.oninput = () => valueL.textContent = sliderL.value;
    sliderR.oninput = () => valueR.textContent = sliderR.value;

    function showStatus(msg, isError = false) {
      status.textContent = msg;
      status.className = 'status ' + (isError ? 'error' : 'success');
      status.style.display = 'block';
      setTimeout(() => status.style.display = 'none', 3000);
    }

    function sendCmd() {
      const l = sliderL.value;
      const r = sliderR.value;
      fetch(`/cmd?l=${l}&r=${r}`)
        .then(res => res.text())
        .then(txt => showStatus(txt, false))
        .catch(err => showStatus('发送失败: ' + err, true));
    }

    function stopMotors() {
      fetch('/stop')
        .then(res => res.text())
        .then(txt => {
          showStatus(txt, false);
          sliderL.value = 0;
          sliderR.value = 0;
          valueL.textContent = '0';
          valueR.textContent = '0';
        })
        .catch(err => showStatus('停止失败: ' + err, true));
    }

    // Poll telemetry every 500ms
    setInterval(() => {
      fetch('/telemetry')
        .then(res => res.json())
        .then(data => {
          curL.textContent = data.l.cur.toFixed(1);
          curR.textContent = data.r.cur.toFixed(1);
        })
        .catch(() => {});
    }, 500);
  </script>
</body>
</html>
)rawliteral";

#endif
