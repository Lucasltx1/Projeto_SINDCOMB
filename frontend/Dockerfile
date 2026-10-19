FROM node:22-alpine

WORKDIR /app

COPY . .

RUN corepack enable

RUN yarn install --immutable

RUN yarn build

CMD ["yarn", "start"]