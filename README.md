# 精装选配原型

面对面选配的第一版骨架：开发商发布试点项目，客户先选风格，再选天花、地面、墙面，报价按示意单价即时重算，三维房间可以旋转，材质跟着方案变。界面文案是简体中文。

这是可本地跑通的 P0，不是生产系统。验证码、后台账号、对象存储和图像接口都是占位，不要部署到公网。

## 仓库结构

```text
apps/api        FastAPI、报价、导入、导出、AI/队列占位、worker
apps/web        Next.js：客户 H5（/c）和开发商后台（/admin）
packages/catalog  种子目录：试点项目、两个户型、三种风格、示例洁具价表
docker-compose.yml  Postgres 16 + Redis 7
```

部位报价和集采价表是两套数据。客户合计来自风格方案 SKU；集采表按品类存放（综合、马桶、洁具、电器、橱柜），本阶段只导入一张表示例，不参与报价。

## 本地运行

需要 Docker、Python 3.11+、Node.js 20+。

```bash
cp .env.example .env
docker compose up -d
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -r apps/api/requirements.txt
```

开三个终端：

```bash
# 1. API  http://127.0.0.1:8000   文档 http://127.0.0.1:8000/docs
cd apps/api
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. 队列消费者（可选；不启动也不影响页面，任务会停在未确认）
cd apps/api
.venv/bin/python -m app.worker

# 3. Web  http://localhost:3000
cd apps/web
npm install
npm run dev
```

API 启动时会建表。库是空的就会写入种子；之后重启会更新风格单价和分房面积，不会覆盖客户已经改过的方案，也不会把已上传的图纸改回占位。

改了表结构时，删掉数据再启动：

```bash
docker compose down -v
docker compose up -d
```

如果本地用的是 SQLite（例如 `DATABASE_URL=sqlite+pysqlite:///./var/fitout.db`，文件在 `apps/api/var/fitout.db`），先停掉 API，再删库后重启。演示项目 `gz2019-003` 会重新挂上客厅天花/墙面/地面/灯具、主卧柜、公卫洁具和玄关入户门。旧库不会自动补这些挂品：

```bash
rm -f apps/api/var/fitout.db
```

启动时也会把旧库里 `schemes.style_id` 的非空约束拆掉，共享 SKU（洁具、柜体等，不绑定风格）才能写进去。删文件是干净重来的办法。

测试：

```bash
cd apps/api && .venv/bin/pytest
```

测试使用临时 SQLite，不碰本机 Postgres。

## 演示账号

| 角色 | 入口 | 账号 |
| --- | --- | --- |
| 客户 | http://localhost:3000/c/login | 任意 11 位手机号，验证码 `123456` |
| 演示客户 | 同上，`13800138000` | 已有 A 户型轻奢方案 `sel_demo` |
| 开发商 | http://localhost:3000/admin/login | `admin` / `demo1234` |

建议路径：客户登录 → 项目 `GZ2019-003` → 选 A 或 B 户型 → 选风格 → 改天花/地面/墙面（看报价和房间材质）→ 提交并下载报价 PDF。后台「客户方案」打开同一条档案。

## 种子数据

项目：金辉惠阳展示区样板房，编号 `GZ2019-003`，已发布。

- A 户型约 86 ㎡，三室两厅一厨一卫。计价面积 60.6 ㎡（不含生活阳台 4.5）。
- B 户型约 96 ㎡，三室两厅一厨两卫。计价面积 69.6 ㎡（不含生活阳台 4.6）。
- 分房面积是样板房摘录的净面积，不等于建筑面积。
- 每个户型有平面图 PDF 和用量图 DWG 两条占位记录，文件本身未入库，后台可上传替换。
- 三种风格 × 天花/地面/墙面 × 三套方案。每部位的方案 1 是默认。
- 硬装 2500 元/㎡、软装 3500 元/㎡按建筑面积只作参考，不加进部位合计。
- 示例洁具价表在 `packages/catalog/sample_sanitary.csv`，启动时已导入。后台也可以再导 CSV 或 XLSX。

奶油风方案 1、A 户型的核对数字：`(180 + 168 + 85) × 60.6 = 26239.80` 元。

## 报价规则

天花、地面、墙面使用同一块室内计价面积：有分房时，把 `counts_toward_finish` 的房间加总（生活阳台排除）；没有分房时，用户型上填写的计价面积，再没有就用建筑面积。

九类在选配页并列，先点大项，再进方案或房间，再逐件。每件有示例图和数量。灯具仍由天花方案带出，例如「客厅天花 · 9 个射灯／筒灯」。全屋定制进主卧后，衣柜、书柜、床头柜可单独去掉。入户门仍是整户一件。天花、地面、墙面的面层仍按 `单价 × 计价面积`。

示例产品库在管理端「产品库」，九类都有自制 SKU。手册和图包先待确认再入库。项目页「部位挂品」把型号挂到房间。给工程师的步骤见 [docs/工程师操作说明.md](docs/工程师操作说明.md)。这一版做到和没做到的清单见 [docs/交付说明-看得出规模.md](docs/交付说明-看得出规模.md)。

材质样张不用登录：`/preview/finishes` 三套并排；单套截图用 `/preview/finishes?style=cream`、`?style=european`、`?style=light_luxury`。贴图是程序生成的木纹、砖缝、石纹和漆面，不是品牌实拍。

换方案会立刻重算，不把单价快照进档案。一户一档只在开发商后台，客户路径进不去。

## 还没接上的部分

- 对象存储：`LocalObjectStorage` 写到 `apps/api/var/storage`。以后换成 OSS/S3 时替换这一层。
- Redis 队列：`queue:ai`。Redis 不在时任务仍写在 `worker_jobs`。
- 场景生成：保存客户上传的家具照片，返回占位。计划接入阿里云百炼 DashScope 或火山引擎。环境变量 `DASHSCOPE_API_KEY`、`VOLCENGINE_API_KEY` 留空。
- 户型识别：不回写房间。计划接入 Qwen-VL 或豆包视觉。`QWEN_API_KEY`、`DOUBAO_API_KEY` 留空。
- 图册导出：ZIP 里只有说明和 manifest，没有效果图。
- 报价 PDF 使用随仓库附带的 Droid Sans Fallback（Apache 2.0，见 `apps/api/app/fonts/`）。

三维有两层。材质预览仍用 `apps/web/public/textures/` 的程序贴图，只表现天花、地面、墙面。选配首页的「房间落位」把已勾选的柜、灯、门、洁具按尺寸放进户型房间，位置按房间面积排开，不是施工图对齐。`/preview/model` 可看自制示例门和示例柜。生模接口无 Key 时只做通用件，不发付费请求。

## 不做

集采全模块、电子签和支付、微信小程序上架、多租户、施工 BIM、原生 App、一次导入多张品类 Excel。

## 需求备忘

后续类目以 [docs/REQUIREMENTS-九类选配.md](docs/REQUIREMENTS-九类选配.md) 为准：客户选配从天花／地面／墙面扩到九类（含柜体、洁具、入户门、厨房电器、灯具、开关插座）。一户一档只给营销端和开发商看，不对客户开放。未另行授权前不接 AI Key、不出真渲染。
