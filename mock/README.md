# ABL 触发 Mock（不改业务源码的模拟数据方案）

公司机器人（<内网机器人地址>）在公司外/离线不可达时，用以下任一方式模拟 ABL 云端数据。

## 方案 A：纯前端注入（最快，无需服务）

在 ByFAB 页按 F12 → Console 粘贴执行（把"模拟数据"写进项目自身的 ABL 缓存，
F5 后首屏即有值；同一小时内不发起请求，正好验证"首屏直显旧数据"）：

```js
(function () {
  const now = new Date(), p = n => String(n).padStart(2, '0');
  const hk = now.getFullYear() + p(now.getMonth() + 1) + p(now.getDate()) + p(now.getHours());
  const fields = {
    title: 'OOS报警数', unit: '次数',
    xAxis: ['W2634', 'W2635', 'W2636', 'W2637'],
    series: [
      { name: '2A', data: [1, 0, 2, 1] },
      { name: '2B', data: [3, 2, 5, 4] },
      { name: '2C', data: [0, 1, 1, 0] },
      { name: '2D', data: [1, 2, 0, 1] },
    ],
    wow: null,
  };
  localStorage.setItem('byfab_abl_cache_v1', JSON.stringify({ savedAt: Date.now(), hourKey: hk, fields }));
  location.reload();
})()
```

想模拟"数据过期后触发刷新/失败重试"：把 `savedAt: Date.now()` 改成 `Date.now() - 2 * 3600 * 1000`
（2 小时前）再执行，进页面会看到静默拉取与重试链。

## 方案 B：独立 Mock API 服务（走完整"拉取"流程）

1. 启动服务（默认 127.0.0.1:8001）：
   ```
   python mock/abl_mock_server.py
   ```
2. 让前端指向它（不改业务代码，仅新增环境变量文件）：
   ```
   copy frontend\.env.development.local.example frontend\.env.development.local
   ```
   （内容：`VITE_API_BASE=http://127.0.0.1:8001/api`）
3. `npm run dev` → 打开 By FAB 页：ABL 触发走 Mock 拉取（数值每分钟轻微浮动），
   「↻ 重新查询」/跨小时静默刷新都能观察到；关掉 Mock 服务可观察"旧数据常驻 + 失败重试"。
4. 用完恢复真实后端：删除 `frontend/.env.development.local` 即可。

> 注意：方案 B 会把整页 API 基址指向 Mock（Mock 只响应 `/byfab/abl/`，其余返回 404），
> 仅适合单独验证 By FAB 页；要同时用预排/决议等真实功能时请先恢复 env。

## 说明
- 均为开发/演示用 mock，**不修改任何业务源码**；
- Mock 返回结构与真实后端代理一致：`{success:true, data:{echarts JSON}}`，
  xAxis 含 WoW 尾列、yAxis.name=次数、series 为 2A-2D 原始 W 编号。
