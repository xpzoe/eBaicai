# 桌面宠物

一个无依赖的 Python 桌面宠物原型，适合先验证玩法和交互。

## 运行

```powershell
python desktop_pet.py
```

## 操作

- 左键拖拽：移动宠物
- 左键双击：摸摸头
- 右键：打开菜单，可以喂食、散步、睡觉或退出
- Esc：退出

## 当前功能

- 透明置顶窗口
- 待机、散步、吃东西、开心、睡觉状态
- 饥饿、能量、亲密度三个状态条
- 自动眨眼、走路、说话气泡
- 自动存档和角色配置

## 配置文件

`pet_state.json` 是运行存档，程序会自动维护：

- `hunger`：饥饿值，越高越饿
- `energy`：能量
- `affection`：亲密度
- `x` / `y`：窗口位置
- `last_seen`：上次保存时间，用来计算离线变化

`pet_profile.json` 是角色设定，可以手动修改：

- `name`：宠物名字，也是窗口标题
- `appearance`：外观颜色
- `personality.energy_style`：`lazy`、`normal` 或 `active`
- `personality.walk_chance`：自动散步概率，0 到 1
- `personality.idle_talk_chance`：待机说话概率，0 到 1
- `lines`：不同事件下会说的话

修改 `pet_profile.json` 后，重新运行程序即可生效。

后续可以继续加托盘图标、开机自启、更多动作帧、换装、AI 对话或定时提醒。
