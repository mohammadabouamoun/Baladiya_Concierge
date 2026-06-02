FROM python:3.11-slim

WORKDIR /app

COPY requirements-chatbot.txt .
RUN pip install --no-cache-dir -r requirements-chatbot.txt

COPY chatbot/ ./chatbot/

EXPOSE 8501

CMD ["streamlit", "run", "chatbot/pages/cms.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
