FROM python:3.11-slim

# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1

# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY telegram-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY telegram-bot/ .

# Expose port 7860 for Hugging Face Spaces health check
EXPOSE 7860

# Command to run the bot
CMD ["python", "bot.py"]
