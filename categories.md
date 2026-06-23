# Categories

Use these category and subcategory enums.

## Category Map

- 食品餐饮: 早餐, 午餐, 晚餐, 正餐, 外卖, 快餐, 小吃, 夜宵, 零食, 休闲零食, 水果, 生鲜, 饮料, 饮料酒水, 聚餐, 请客吃饭
- 出行交通: 打车, 公交地铁, 加油, 充电, 火车, 飞机, 租车, 停车费, 高速费, 通行费, 酒店住宿, 景区门票, 维修
- 购物消费: 服饰运动, 数码, 手机数码, 日常家居, 家居用品, 日用百货, 礼品, 纪念品, 祭祀用品, 虚拟充值, 外汇, 交通工具, 邮寄
- 服饰美容: 服装
- 居家生活: 住宿, 水费, 洗护, 政务, 邮寄, 电费
- 生活服务: 超市, 快递, 清洁用品, 燃气费
- 医疗健康: 挂号, 门诊, 检查费, 药品, 买药, 医院看病
- 休闲娱乐: 旅游度假, 棋牌桌游, 酒吧, 游戏, 游戏充值, 游戏购买, KTV
- 收入: 工资, 报销, 补贴, 其他
- 还款: 白条还款, 月付还款
- 转账: 个人转账

## Legacy Aliases

Existing data may contain these aliases. Normalize them during analysis:

- `健康医疗` -> `医疗健康`
- `停车` -> `停车费`
- `高速费用` -> `高速费`
- `酒水饮料` -> `饮料酒水`

## Classification Rules

- `收支类型=收入` should use `类别=收入`.
- `收支类型=还款` should use `类别=还款`.
- `收支类型=转账` should use `类别=转账`.
- Unknown category or subcategory: use `待确认` in notes, do not invent silently.
