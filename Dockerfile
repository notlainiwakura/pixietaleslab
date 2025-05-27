# Use the official Python image.
FROM python:3.9-slim

# Set work directory
WORKDIR /app

# Install system dependencies (if you use any, e.g., for reportlab or pillow)
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose the port Cloud Run expects
EXPOSE 8080

# Run the app with uvicorn
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8080"]
