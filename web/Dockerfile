FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install

COPY index.html ./index.html
COPY vite.config.js ./vite.config.js
COPY src ./src

EXPOSE 4000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "4000"]

