# 目标站点定义

## 1. 阳光高考（CHSI）

### 目标数据
- 专业信息
- 院校信息

### 入口
- 专业列表：
  https://gaokao.chsi.com.cn/zyk/zybk/
- 院校列表：
  - 第一页
    https://gaokao.chsi.com.cn/sch/search--ss-on,option-qg,searchType-1,start-0.dhtml
  - 第二页
    https://gaokao.chsi.com.cn/sch/search--ss-on,option-qg,searchType-1,start-20.dhtml
  - 最后一页
    https://gaokao.chsi.com.cn/sch/search--ss-on,option-qg,searchType-1,start-2900.dhtml

### 专业页特点
- 列表页为动态表格结构
- 存在多级筛选：
  - 培养层次
  - 门类
  - 专业类
- 详情页至少包含：
  - 基本信息
  - 开设院校
  - 开设课程
- 专业详情页链接模式：
  - `zykzybkdetail{specId}`
- 专业院校页链接模式：
  - `zykzybkksyxPage?specId={specId}`
- 专业课程页链接模式：
  - `zykzybkkskcPage{specId}`

### 院校页特点
- 列表页为卡片式分页列表
- 每条院校记录包含：
  - 学校名称
  - 主管部门 / 隶属信息
  - 办学层次 / 类型标签
  - 院校满意度
  - 详情页链接
- 详情页为多导航结构，至少包含：
  - 学校首页
  - 学校简介
- 院校详情页链接模式：
  - `schschoolInfo--schId-{schId}.dhtml`
  - `schschoolInfoMain--schId-{schId}.dhtml`
  - `schschoolInfo--schId-{schId},categoryId-{categoryId},mindex-{mindex}.dhtml`
  - `schlistzyjs--schId-{schId},categoryId-417809,mindex-3.dhtml`

### 采集建议
- CHSI 统一使用 Playwright
- 列表页负责稳定提取入口与基础字段
- 详情页按页面类型分函数解析
- 所有相对链接转绝对 URL

---

## 2. 学职平台（XZ）

### 目标数据
- 专业信息
- 职业信息

### 入口
- 专业：
  https://xz.chsi.com.cn/major/index.action
- 职业：
  https://xz.chsi.com.cn/career/index.action

### 特点
- 专业列表页存在筛选器、搜索、分页
- 专业详情页为四标签结构：
  - 基本信息
  - 开设院校
  - 开设课程
  - 毕业发展
- 职业页结构相对简单
- 使用 Playwright 评估实现