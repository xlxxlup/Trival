from zai import ZhipuAiClient

client = ZhipuAiClient(api_key="644a19dba0604174a3c223da87678c24.5QSlMiDsjVwwLQiv")

response = client.web_search.web_search(
   search_engine="Search-Std",
   search_query="橘子洲头 评分 地址 开放时间 预约实名 旅游攻略",
   count=5,  # 返回结果的条数，范围1-50，默认10
   # search_domain_filter="www.sohu.com",  # 只访问指定域名的内容
   search_recency_filter="noLimit",  # 搜索指定日期范围内的内容
   content_size="medium"  # 控制网页摘要的字数，默认medium
)
print(response)
