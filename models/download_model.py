import os

# 必须放在导入 sentence_transformers 之前
os.environ.pop("HF_ENDPOINT", None)

# 使用你的本地代理端口
os.environ["HF_TOKEN"] = "你的token"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7892"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7892"
os.environ["ALL_PROXY"] = "http://127.0.0.1:7892"

from sentence_transformers import SentenceTransformer

model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
save_path = r"D:\A_Projects\back_service\eduforge_ai_service\models\paraphrase-multilingual-MiniLM-L12-v2"

model = SentenceTransformer(model_name)
model.save(save_path)

print(f"模型已下载并保存到: {save_path}")