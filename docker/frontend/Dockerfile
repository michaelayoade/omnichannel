FROM node:18-alpine

# Set working directory
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy project files
COPY . .

# Build for production
ENV NODE_ENV=development

# Set proper permissions
RUN chown -R node:node /app
USER node

# Expose port
EXPOSE 5173

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
