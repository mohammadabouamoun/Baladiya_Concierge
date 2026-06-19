FROM python:3.11-slim

WORKDIR /app

COPY requirements-chatbot.txt .
RUN pip install --no-cache-dir -r requirements-chatbot.txt

COPY platform_manager/ ./platform_manager/
COPY .streamlit/ ./.streamlit/

EXPOSE 8502

CMD ["streamlit", "run", "platform_manager/app.py", \
     "--server.port=8502", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
