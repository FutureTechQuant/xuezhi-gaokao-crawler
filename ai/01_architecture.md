# 爬虫项目架构

## 技术选型
- Python 3.11
- aiohttp
- BeautifulSoup / lxml
- SQLite / MongoDB

## 项目结构
project/
  spiders/
  parsers/
  pipelines/
  storage/
  utils/
  config/

## 数据流
请求 -> 解析 -> 提取 -> 清洗 -> 存储

## 原则
- 解耦
- 可扩展
- 可重试
