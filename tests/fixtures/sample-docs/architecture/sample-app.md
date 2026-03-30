# Sample App Architecture

## Overview

A minimal Express.js application with user management.

## Components

- **Express Server** - HTTP server and routing
- **User Model** - Data model for user entities
- **Auth Middleware** - Authentication middleware

## Data Flow

1. Client sends request
2. Auth middleware validates token
3. Route handler processes request
4. Model retrieves data
5. Response sent to client
