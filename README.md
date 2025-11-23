# Customer Microservice

This repository contains the **Customer Composite Service**, which aggregates data from the following two atomic services:

- **Customer Atomic Service** (customer core data)  
- **Customer Address Atomic Service** (address records)

The composite service exposes a unified REST API for all customer-related operations.

---

## 🚀 How to Run the Services (Local Development)

### **Composite Service (this service)**
```
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### **Customer Atomic Service**
```
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### **Customer Address Atomic Service**
```
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### **Python Version**
```
Python 3.12.7
```

---

## 🔧 Environment Variables

This service calls the atomic services using URLs provided via environment variables.

| Variable | Description | Example |
|---------|-------------|---------|
| `CUSTOMER_SERVICE_URL` | URL for the customer-atomic-service | `http://localhost:8000` |
| `ADDRESS_SERVICE_URL`  | URL for the address-atomic-service | `http://localhost:8001` |
| `FASTAPI_PORT`         | Port for this composite service     | `8002` |

---

## 📄 .env.example

```
CUSTOMER_SERVICE_URL=http://localhost:8000
ADDRESS_SERVICE_URL=http://localhost:8001
FASTAPI_PORT=8002
```

> **Note:**  
> This composite service does **not** connect to Cloud SQL directly.  
> Only the atomic services require database environment variables.

---

## 🗄️ Cloud SQL Integration (Sprint 2)

A dedicated Cloud SQL MySQL database was created for the Customer domain as part of Sprint 2.

### **Database Information**

```
DB Name: customer_db
DB User: customer_svc
Public IP: 35.231.90.93   (for local testing)
Private IP: 10.201.0.3    (for VM/production via VPC)
Port: 3306
```

Database environment variables such as `DB_HOST`, `DB_USER`, etc., should be placed in the **atomic microservices**, not here.

---

## 🧪 Testing

Once all services are running, access:

- Composite API Docs → http://localhost:8002/docs  
- Health Check → http://localhost:8002/health  

---

## 📦 Deployment Notes

- In cloud deployment, this service calls the atomic microservices running inside the VPC.
- The database is accessed by the atomic services using the Private IP via Private Service Access (PSA).
- This repo only requires the environment variables listed above.

---

## ✔️ Summary

- Composite service: runs on port **8002**
- Calls atomic services at **8000** and **8001**
- No direct DB connection in this codebase
- Cloud SQL setup completed in Sprint 2 (for atomic services)