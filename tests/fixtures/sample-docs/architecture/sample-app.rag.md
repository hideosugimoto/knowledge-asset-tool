# Sample App RAG Document

## SYSTEM_OVERVIEW

A minimal Express.js web application for user management.

## COMPONENTS

- Express server (app.js)
- User model (models/user.js)
- Index router (routes/index.js)
- Auth middleware (middleware/auth.js)

## FLOW

Request -> Auth Middleware -> Router -> Controller -> Model -> Response

## DEPENDENCY

- express ^4.18.0
- ejs ^3.1.0

## ERROR_HANDLING

Standard Express error middleware pattern.

## BUSINESS_RULES

- Users must be authenticated to access /users endpoint
- All responses are JSON format

## CONSTRAINTS

- SQLite for development, PostgreSQL for production
- Token-based authentication required

## KEYWORDS

express, nodejs, rest-api, user-management, authentication
