FROM node:22-alpine

WORKDIR /app

COPY package.json .
RUN npm install

# O código-fonte é montado via volume — não copiado na imagem
# Isso garante que alterações locais reflitam instantaneamente (HMR)

CMD ["npm", "run", "dev"]

