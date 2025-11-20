# Customer Microservice
Commands to run the services:
Customer Microservice (Main Composite) : uvicorn main:app --host 0.0.0.0 --port 8002 --reload
Customer Address Atomic Service : uvicorn main:app --host 0.0.0.0 --port 8001 --reload
Customer Atomic Service: uvicorn main:app --host 0.0.0.0 --port 8001 --reload
