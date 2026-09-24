把机器人照片放进这个文件夹（frontend/public/assets/）。

默认文件名：robot.png
本项目 16 张卡片共用这一张图 —— 只放一次，页面上自动出现 16 次。

换图步骤：
  1) 把照片命名成 robot.png 放到这里（覆盖旧的即可）
  2) 在 frontend 目录执行构建，再把产物同步到 backend/static/frontend/
     （命令见项目「机器人图片替换指南」/ 上次对话说明）
  3) 浏览器 F5 刷新

如果照片是 jpg：放成 robot.jpg，并把
  frontend/src/views/RobotAutomationView.vue 里的
  const ROBOT_IMG = '/assets/robot.png'  改成  '/assets/robot.jpg'

注意：图片必须放在 /assets/ 下（本目录即对应线上 /assets/），
      放别处会被前端路由兜底成 index.html，图片取不到。
