# bot/ — 吉祥物动画引擎（bloub）

本目录引擎代码源自开源项目 **bloub**（Jeremy Pereira, MIT License）：
https://github.com/jeremy-prt/bloub

一个 SVG 智能小球：单个主体形状在 14 种状态间形变（idle/thinking/orbit/
burst/comet…），双眼为主体上的遮罩孔洞独立形变。纯 TypeScript、零框架、
零依赖，`engine.sample(t)` 是时间的纯函数。

React 渲染层在 `src/components/BotAvatar.tsx`（本项目自有代码）。

- 引擎原始文件：math / shape / profiles / states / cycles / face / eyefit /
  decor / repere / skins / expressions / engine（未改动逻辑，仅随项目 TS 配置编译）
- 授权：MIT，原文见同目录 `LICENSE`
- 与原项目无官方关联；"Grok"/"x.ai" 商标归其权利人所有
