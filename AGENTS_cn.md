# 项目指引

[English](AGENTS.md) | 简体中文

## 技术栈与设计

README.md 和 Cargo.toml 是当前设计/构建参考。本项目有两种可替代后端：Rust/Cargo 与仅标准库的 Python 3。保持 Python HTML_CONTENT 和 static/index.html 相同。保留 BlackBerry Passport 所需的前端 ES5 兼容性；仅 Node 语法检查不能证明 ES5 兼容。

## Project gate

<!-- project-gate:start -->
按当前任务确定作者/评审者，不按 agent 产品名称确定。作者提交前运行 `./check.sh --fast`，交付评审或移交前运行 `./check.sh`。修复诊断原因并重跑，不为通过而弱化检查。评审者读取代码 diff 前，对准确目标运行 `./check.sh`；失败就返回诊断并停止，不修复源码。缺 gate 阻止评审，相关修改使先前通过结果失效。每个 clone 首次由作者使用时，运行 `./scripts/install-hooks.sh`。技术栈变化时用 project-gate 更新检查，保留自定义检查。hook 要求提交前全部未忽略的源码改动已暂存，推送前 HEAD 干净；部分暂存或推出其他 ref 需要明确采用快照检查方式。
<!-- project-gate:end -->

## 验证范围

快档覆盖 shell 语法、改动行空白、rustfmt、锁定依赖的离线 Cargo 构建/类型检查、警告视为失败的 Clippy、Python 语法/缩进、网页副本一致性及内嵌 JavaScript 语法。完整档增加实际发现且非空的 Rust/Python 测试集。测试使用 mock/本地回环，不对真实电视运行机械检查。离线 gate 前需准备依赖，构建产物使用 `target/project-gate`，与临时评审构建产物分开。超出缩进的 Python 格式化、Python 类型检查、ES5 解析、sanitizer、audit 及真实设备/浏览器验证不属于已配置检查。

## 评审记录与语言

遵循 CODE_REVIEW.md 的稳定问题编号、修复提交记录、独立核验关闭及三轮里程碑上限。保持中英文评审报告同步。新增代码、注释、日志使用英文；文档使用 `.md` / `_cn.md` 双语文件，提供语言切换链接并同步内容。

- 开发和评审时，以英文文档为工作依据，不再读取表意相同的中文副本。中文版本供人类读者阅读，继续保持完整和同步。仅在用户明确要求、用户引入或手写尚无英文对应版本的中文输入，或需要修改/核对译文相关段落时读取中文。不为寻找额外信息而读取两份同步版本。交流语言遵循用户偏好。
