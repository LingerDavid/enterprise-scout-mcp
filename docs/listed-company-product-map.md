# 上市公司档案 — 服务价值投资

本文是产品与数据契约。采集通道、MCP 工具和页面尚未实现。工商主路径仍是 ENScan；利润、营收、资产、主营构成、股东名册来自定期报告，不能靠加 ENScan field 补齐。

## 目的

档案给价值投资提供可核对的输入。系统只填披露里能算出的格子。倍数、`unrated` 状态和价值风格袖套不在本仓生成，由 tradecraft 研究笔记读取这些表之后产生。本仓不跑折现，不给目标价，也不标注「便宜 / 贵」或「护城河」。

固定回答六件事。填不满就留白。

1. **赚什么钱** — 收入与毛利来自哪些分部，是否集中，毛利率是否靠某一块。
2. **赚得是否实在** — 归母、扣非、经营现金流是否同向；销售收现相对收入。
3. **能否持续** — 至少三个年报上的毛利率、归母净利率、扣非净利率序列（只展示，不断言）。
4. **钱用去哪** — 资本开支、分红、回购、筹资现金流是造血还是输血。
5. **账上压什么** — 应收、存货、商誉、有息负债相对收入与权益。
6. **谁控制、有没有质押** — 实控人终点、前十大合计、控股股东质押占其持股。

库先收上市公司定期报告。操作一条读路径：按发行人 / 证券取表，某一视图没有行就跳过，不写「非上市则走工商」分支，也不用经营范围顶替分部收入。工商 `edges/equity` 与上市表并列。

下游对齐：`security_id` 形如 `SSE:600519`、`SZSE:000001`、`BSE:830000`。tradecraft 行情代码形如 `600519.SH`。映射在 tradecraft 笔记里做，本仓不按公司名称模糊匹配。决策日只能使用 `document` 日期不晚于该日的行。

第一版覆盖 A 股非金融（主板 / 创业板 / 科创板）。银行、保险、券商另册。H 股仅作并列 `security_id`；财务默认用境内合并报表。

---

## 会计口径

- 默认 **合并**（`scope=consolidated`）。母公司报表若入库用 `scope=parent`，瀑布与现金质量视图只读合并。
- 会计准则以定期报告声明为准（通常 CAS）。不做 IFRS 重编。
- 金额：字符串十进制，单位固定元，`currency=CNY`。原稿为千元 / 万元时写入前换算，并记 `scale_in_source`。
- 重述：同一 `(issuer_id, period, scope, statement, item_code)` 后写入覆盖先写入，保留 `supersedes_ref`。读最新；多年对比若跨重述，标「含重述」。
- 扣非归母：只用年报「非经常性损益项目及金额」表给出的汇总数，不自编扣非公式。
- 期间：`YYYY` 年报、`YYYYH1` 中报、`YYYYQn` 季报。同比只在同类之间。持续性主图只用年报。季报通常无分部 → 产品视图跳过。

---

## 标识

| ID | 含义 | 挂载 |
|----|------|------|
| `issuer_id` | 统一社会信用代码 | facts、segments、listed_control、subsidiaries |
| `security_id` | `{exchange}:{code}`，如 `SSE:600519` | identity、holders、capital |
| `document_id` | 公告编号或巨潮文件名 | 一切出处的稳定键 |
| `period` | 报告期 | 财务与分部 |
| `as_of` | `YYYY-MM-DD` | 名册、质押、控制关系公告日 |

查询键（简称、代码、信用代码、法定名称）归一到 `(issuer_id, security_id)`。A+H：财务挂发行人；持股图按证券切换，默认 A 股。

---

## 档案结构

```
上市公司档案（六问）
├─ 身份条          代码 / 交易所 / 板块 / 证监会行业 / 实控人一句话
├─ 赚什么钱        产品地图（一种切法：行业 | 产品 | 地区）
├─ 赚得是否实在    利润瀑布 + 口径三列 + 现金流对照
├─ 能否持续        三年以上年报利润率序列
├─ 钱用去哪        资本配置表
├─ 账上压什么      资产负债关注科目
└─ 谁控制          控制路径 | 直接持股 | 向下投资（三张图）
```

各问用自己的时点：财务与分部跟 `period`；名册与质押跟 `as_of`。一次只铺开一块主图，其余切换。每个展示数字可点回 `document_id`。

---

## 1. 股权穿透（谁控制）

三种关系，不串成「实控人 → 控股股东 → 前十大 → 公司 → 子公司」一条链。控股股东通常是前十大中的一名，高亮该行，不是前十大的父节点。

**控制路径。** 只画年报或权益变动书写明的链条。边上标明持股或表决权。一致行动人是路径参与方，不是固定兄弟节点。终点：自然人 / 国资 / 外资 / 声明无实际控制人。上限 6 跳。不上溯工商猜实控人。

**直接持股。** 前十大 + 派生「其他」（`1 - Σ 前十大占比`）。节点宽度 = 占总股本比（同一本股本的划分）。质押、冻结写在股东上，分母是该股东持股，公告日独立。

**向下投资。** 第一层用年报子公司清单：名称、直接持股、是否纳入合并（以合并范围为准，不以「>50%」推断）。更深按节点读现有 `edges/equity`，标 `source=registry`。分支机构不进图。

名册与工商出资不一致时不写 `conflicts`；证券层以名册为准。

---

## 2. 利润与质量（赚得是否实在 / 能否持续）

### 利润瀑布

科目顺序固定，不是父拆子树。分行业 / 分产品 / 分地区不挂在瀑布下（见产品地图）。

```
营业收入
− 营业成本
= 毛利
− 税金及附加 − 销售 − 管理 − 研发 − 财务费用
± 其他收益、投资收益、公允价值变动、信用减值、资产减值、资产处置
= 营业利润
± 营业外收入 / 支出
= 利润总额
− 所得税
= 净利润
= 归母净利润 + 少数股东损益
```

旁挂（不插入瀑布）：扣非归母净利润。

`gross_profit`：有披露用披露；否则仅当收入与成本齐全时派生，并标 `derived=true`。

### 口径与含金量

三列并列，不合成一个分：归母净利 | 扣非归母 | 经营活动现金流净额。

| 对照 | 公式 | 缺则 |
|------|------|------|
| 销售收现 / 营业收入 | `cash_from_sales / revenue` | 跳过 |
| 经营现金流 / 净利润 | `cfo / net_profit` | 跳过 |
| 近似业主盈余输入 | `cfo - capex_cash` | 跳过；文案写「经营现金流减购建支出」，不随便称 FCFF/FCFE |

### 持续性

同一 `item_code`、合并口径、至少三个年报：毛利率、归母净利率、扣非净利率折线。中报不进本图。跨重述标「含重述」。

### 资产负债关注科目

关注科目，子项之和不必等于总资产。合计只来自报表合计行。展示期末、期初、占总资产比。第一版不设红黄阈值。

资产：货币资金、交易性金融资产、应收票据、应收账款、应收款项融资、预付款项、存货、合同资产、其他流动资产、长期股权投资、固定资产、在建工程、无形资产、商誉、递延所得税资产、资产总计。  
负债：短期借款、应付票据、应付账款、合同负债、长期借款、应付债券、租赁负债、负债合计。  
权益：归母权益、少数股东权益、权益合计。

### 资本配置（钱用去哪）

并列表（有则显示）：`capex_cash`、`dividends_paid`、`buyback_cash`、`cff`。缺项跳过该格。

### 同行

证监会行业（报告披露）。同行业、同年报、合并口径、库内样本 ≥8 才显示营收与净利率分位。文案写「库内分位」。可比公司仅用户指定。申万分类另源配置，不从年报推断。

ROE：`net_profit_parent / average(equity_parent 期初, 期末)`；缺期初不算。

---

## 3. 产品地图（赚什么钱）

服务盈利来源与毛利结构，不是产品目录。形态：主体居中，一种切法的划分在周围；宽度 = 该切法下收入占公司收入比；节点另标毛利贡献。

切法平级三选一：`industry` | `product` | `region`。禁止把三种切法的数字加总或并成一份总收入。

- 年报只披露到板块 → 下层显示「未拆分」，不发明产品线或 SKU。
- 无收入且无成本 → 不进地图；正文「主要从事」只作点开摘录。
- 收入对不上 → 先放披露的「分部间抵消」节点（`kind=elimination`）；否则标与营业收入差额，不设容差糊弄。
- 改名且未声明可比 → 新 `segment_id`，标「本期不可比」。
- 交叉矩阵（产品 × 地区）第一版不做；无矩阵不叉乘。
- 市占 / 排名：仅公告原文有出处才显示。

与利润瀑布联动：毛利行「按分部看」打开本图，携带 `(issuer_id, period, kind, scope)`。公司级费用、减值、所得税不摊进分部。分部比较停在毛利。

---

## 比较公式（读时算，不入库）

一次视图：一个指标、一种切法、一个 period 类、一个 scope。缺任一输入 → 该格跳过，不借别期或别切法。

| 比较 | 公式 | 跳过 |
|------|------|------|
| 同比 | `(本期 − 同期) / \|同期\|` | 缺同期或同期为 0；年报不对中报 |
| 占营收 | `科目 / revenue` | 缺 revenue |
| 毛利率 | `(revenue − cost) / revenue` | 缺一或 revenue=0 |
| 毛利贡献 | `分部毛利 / 公司毛利` | 缺公司毛利；分部缺 cost 则无该分部贡献 |
| 收入占比 | `分部 revenue / 公司 revenue` | 缺公司 revenue |
| 库内分位 | 同行业同 period 样本百分位 | n < 8 |

禁止：在本仓自建 DCF / WACC / 目标价 / PEG；自编扣非；把净利摊进分部；经营范围拆成产品节点。市值倍数与价值袖套候选由 tradecraft 读取本表后计算。

---

## 数据从哪来

| 内容 | 来源 |
|------|------|
| 三大表、主营构成、前十大、实控人、子公司清单 | 定期报告 / 权益变动书 / 质押公告（披露原文） |
| 代码、交易所、最新报告期；可选申万 | 名册或分类镜像；与披露冲突时披露胜出 |
| 未上市主体更深股权 | 现有 `Dimension.EQUITY` + ENScan，按需 |
| 已抽取年报 | `corpus/listed` |

建议维度（实现时再改 `models.Dimension`）：`listed_identity`、`listed_fundamental`、`listed_segment`、`listed_equity`。一次档案编排这些维度；失败保持 `partial`，不阻断已成功视图。

---

## 仓库形状

追加 parquet，下游去重。毛利率、同比、占比、分位不入库。

| 路径 | 一行是什么 |
|------|------------|
| `warehouse/listed/identity/part.parquet` | 一只证券 |
| `warehouse/listed/facts/part.parquet` | 发行人 × 报告期 × scope × 科目 |
| `warehouse/listed/segments/part.parquet` | 发行人 × 报告期 × 切法下的一个分部 |
| `warehouse/listed/capital/part.parquet` | 证券 × 名册日的股本 |
| `warehouse/listed/holders/part.parquet` | 证券 × 名册日 × 一名股东 |
| `warehouse/listed/subsidiaries/part.parquet` | 年报子公司第一层 |
| `warehouse/edges/listed_control/part.parquet` | 控制路径一跳 |
| `warehouse/edges/equity/part.parquet` | 现有工商边，不改列 |

### identity

`issuer_id`, `issuer_name`, `security_id`, `exchange`, `code`, `board`, `csrc_industry_l1`, `csrc_industry_l2`, `list_date`, `is_primary_listing`, `document_id`, `collected_at`

### facts

`issuer_id`, `period`, `scope`, `statement`（`income` / `balance` / `cashflow`）, `item_code`, `label`, `value`, `unit`, `currency`, `scale_in_source`, `derived`, `document_id`, `document_date`（公告日 `YYYY-MM-DD`，决策日过滤用）, `audit_opinion`, `collected_at`, `supersedes_ref`

**利润 item_code（顺序即瀑布序）**  
`revenue`, `operating_cost`, `gross_profit`, `tax_surcharge`, `selling_exp`, `admin_exp`, `rd_exp`, `finance_exp`, `other_income`, `invest_income`, `fv_change`, `credit_impairment`, `asset_impairment`, `asset_disposal`, `operating_profit`, `non_operating_income`, `non_operating_expense`, `profit_before_tax`, `income_tax`, `net_profit`, `net_profit_parent`, `net_profit_minority`；旁挂 `net_profit_parent_ex_nonrecurring`。

**资产负债关注**  
`cash`, `trading_assets`, `notes_receivable`, `accounts_receivable`, `receivables_financing`, `prepayments`, `inventory`, `contract_assets`, `other_current_assets`, `long_term_equity`, `fixed_assets`, `cip`, `intangible`, `goodwill`, `deferred_tax_assets`, `total_assets`, `short_term_borrowings`, `notes_payable`, `accounts_payable`, `contract_liabilities`, `long_term_borrowings`, `bonds_payable`, `lease_liabilities`, `total_liabilities`, `equity_parent`, `equity_minority`, `total_equity`。

**现金流与资本配置**  
`cash_from_sales`, `cfo`, `cfi`, `cff`, `capex_cash`, `cash_end`, `dividends_paid`, `buyback_cash`。

### segments

`issuer_id`, `period`, `kind`（`industry` / `product` / `region` / `elimination`）, `segment_id`, `parent_segment_id`, `name`, `revenue`, `cost`, `comparable_flag`, `document_id`, `collected_at`

`segment_id` = 规范化(`issuer_id` + `kind` + `name`)。无收入且无成本不插行。

### capital

`security_id`, `as_of`, `total_shares`, `float_shares`, `document_id`, `collected_at`

### holders

`security_id`, `as_of`, `rank`, `holder_name`, `holder_type`, `shares`, `pct_total`, `share_class`, `pledge_pct_of_holding`, `pledge_as_of`, `freeze_flag`, `document_id`, `collected_at`

「其他」不入库，读时派生。

### listed_control

`issuer_id`, `as_of`, `hop`, `src_name`, `dst_name`, `ratio`, `ratio_kind`（`ownership` / `voting`）, `is_concert_party`, `endpoint_type`, `document_id`, `collected_at`

### subsidiaries

`issuer_id`, `period`, `name`, `direct_pct`, `consolidated`, `main_business`, `document_id`, `collected_at`

---

## 操作契约

```
resolve(query) → (issuer_id, security_id)
for each view:
  rows = read(table, keys)
  if empty: skip view   # 不是 error
工商 equity: 仅点开某未上市主体时按需
每个数字 → document_id
```

无 `identity` → 整份上市档案跳过。有 identity 缺 `segments` → 只跳过「赚什么钱」。缺现金流行 → 瀑布仍可开，含金量条跳过。

---

## 页面

新页面「上市公司」，不扩爱企查 Tab。爱企查继续服务工商与一层持股。

1. 顶栏：搜索；六问切换（一次一块主图）。
2. 股权：控制路径多跳；直接持股用宽度；质押角标含占自身持股与公告日。
3. 质量：瀑布 + 口径三列 + 现金流对照；点科目看本期 / 同比。
4. 产品：宽度=收入占比；节点写毛利贡献；点开看出处摘录。
5. 底栏：本页 `document_id` 列表。

财务与名册未接入时，不拿爱企查工商树顶前十大。

---

## 实现顺序

1. 标识 + 六表列契约 + `item_code`（设计与列定义代码；采集可后接）。
2. 合并利润瀑布 + 口径三列 + 关注资产负债（最新年报）。
3. 直接持股 + 控制路径。
4. 分行业 / 分产品 / 分地区 + 毛利贡献。
5. 资本配置、三年利润率序列、子公司第一层、库内分位（样本够后）。

每一步可单独展示。无行则跳过，不降级到经营范围或错误切法。
