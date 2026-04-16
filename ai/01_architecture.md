# 爬虫项目架构

## 项目目标
本项目包含两个站点：
- 阳光高考（CHSI）：采集专业信息、院校信息
- 学职平台（XZ）：采集专业信息、职业信息

## 技术选型
- Python 3.13
- Playwright
- 结构化解析：re / lxml / BeautifulSoup（按页面需要选用）
- 输出格式：JSON
- 自动化运行：GitHub Actions

## 架构原则
- 站点隔离：CHSI 与 XZ 分目录维护
- 阶段隔离：列表页、详情页、结构化输出分层实现
- 输出统一：所有脚本输出先写入 output/
- 自动回写：Actions 成功后同步到 data/ 对应目录
- 可恢复：支持 partial 文件，便于失败续查

## 推荐目录结构
project/
  scripts/
    chsi/
      majors.py
      schools.py
    xz/
      majors.py
      careers.py
  parsers/
    chsi/
    xz/
  data/
    chsi-zyk/
    chsi-schools/
    xz-major/
    xz-career/
  output/
  .github/workflows/

## 数据流
页面加载 -> 列表提取 -> URL 收集 -> 详情解析 -> 字段清洗 -> JSON 输出 -> GitHub Actions 同步回仓库