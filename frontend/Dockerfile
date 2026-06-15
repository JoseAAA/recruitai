FROM node:20-alpine

WORKDIR /app

# Install dependencies. Copiar package*.json ANTES del código fuente permite
# que Docker cachee esta capa: si no cambian las dependencias, las
# reconstrucciones reutilizan node_modules y tardan segundos.
COPY package*.json ./
RUN npm install

# Copy source
COPY . .

# Development mode
EXPOSE 3000

CMD ["npm", "run", "dev"]
