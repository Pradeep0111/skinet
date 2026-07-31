# Skinet E-Commerce Application

A full-stack e-commerce application built with .NET 9.0 and Angular 21, featuring a modern shopping experience with real-time notifications, payment processing, and an admin dashboard.

## 🏗️ Architecture

The application follows Clean Architecture principles with a clear separation of concerns:

- **API Layer**: ASP.NET Core Web API controllers and middleware
- **Core Layer**: Domain entities, interfaces, and business logic
- **Infrastructure Layer**: Data access, external services, and implementations
- **Client Layer**: Angular 21 SPA with Material Design and Tailwind CSS

## ✨ Features

### Customer Features
- 🛍️ **Product Catalog**: Browse products with filtering, sorting, and pagination
- 🔍 **Product Search**: Search products by name, brand, and type
- 🛒 **Shopping Cart**: Add/remove items with real-time updates (Redis-backed)
- 💳 **Secure Checkout**: Stripe payment integration
- 📦 **Order Management**: View order history and order details
- 🎟️ **Coupon System**: Apply discount coupons at checkout
- 👤 **User Authentication**: Register, login, and manage account
- 📍 **Address Management**: Save and manage shipping addresses
- 🔔 **Real-time Notifications**: SignalR-powered live updates

### Admin Features
- 📊 **Admin Dashboard**: Manage products, orders, and coupons
- ➕ **Product Management**: Create, update, and delete products
- 📈 **Order Overview**: Monitor and manage customer orders
- 🎫 **Coupon Management**: Create and manage discount coupons

## 🛠️ Tech Stack

### Backend
- **.NET 9.0**: Latest .NET framework
- **ASP.NET Core Web API**: RESTful API endpoints
- **Entity Framework Core 9.0**: ORM for data access
- **SQL Server**: Primary database (Azure SQL Edge compatible)
- **Redis**: In-memory cache for shopping cart
- **ASP.NET Core Identity**: Authentication and authorization
- **Stripe API**: Payment processing
- **SignalR**: Real-time web functionality
- **Repository Pattern**: Data access abstraction
- **Unit of Work**: Transaction management
- **Specification Pattern**: Flexible querying

### Frontend
- **Angular 21**: Modern web framework
- **TypeScript 5.9**: Type-safe JavaScript
- **Angular Material**: UI component library
- **Tailwind CSS 4**: Utility-first CSS framework
- **RxJS**: Reactive programming
- **SignalR Client**: Real-time communication
- **Stripe.js**: Payment UI components
- **Vitest**: Testing framework

## 📋 Prerequisites

- [.NET 9.0 SDK](https://dotnet.microsoft.com/download/dotnet/9.0)
- [Node.js 20+](https://nodejs.org/) and npm 11.6.2+
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (for SQL Server and Redis)
- [Stripe Account](https://stripe.com/) (for payment processing)

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone <repository-url>
cd skinet
```

### 2. Start Database Services
```bash
docker-compose up -d
```

This will start:
- SQL Server (Azure SQL Edge) on port 1433
- Redis on port 6379

### 3. Configure Backend

Update `API/appsettings.Development.json` with your configuration:
```json
{
  "ConnectionStrings": {
    "DefaultConnection": "Server=localhost,1433;Database=Skinet;User Id=sa;Password=Password@1;TrustServerCertificate=true",
    "Redis": "localhost:6379"
  },
  "StripeSettings": {
    "PublishableKey": "your-stripe-publishable-key",
    "SecretKey": "your-stripe-secret-key"
  }
}
```

### 4. Run Database Migrations

Navigate to the API folder and run:
```bash
cd API
dotnet restore
dotnet ef database update
```

The application will automatically seed initial data on startup.

### 5. Start Backend API
```bash
dotnet run
```

The API will be available at:
- HTTP: `http://localhost:5000`
- HTTPS: `https://localhost:5001`

### 6. Install Frontend Dependencies
```bash
cd client
npm install
```

### 7. Start Frontend Application
```bash
npm start
```

The Angular app will be available at `http://localhost:4200`

## 📁 Project Structure

```
skinet/
├── API/                          # Web API Layer
│   ├── Controllers/              # API endpoints
│   ├── DTOs/                     # Data Transfer Objects
│   ├── Extensions/               # Helper extensions
│   ├── Middleware/               # Custom middleware
│   ├── SignalR/                  # Real-time hubs
│   └── Program.cs                # Application entry point
│
├── Core/                         # Domain Layer
│   ├── Entities/                 # Domain models
│   │   └── OrderAggregate/       # Order aggregate root
│   ├── Interfaces/               # Abstractions
│   └── Specifications/           # Query specifications
│
├── Infrastructure/               # Infrastructure Layer
│   ├── Config/                   # Entity configurations
│   ├── Data/                     # DbContext and repositories
│   ├── Migrations/               # EF Core migrations
│   └── Services/                 # External service implementations
│
├── client/                       # Angular Frontend
│   └── src/
│       └── app/
│           ├── Core/             # Core services and guards
│           ├── features/         # Feature modules
│           │   ├── account/      # Authentication
│           │   ├── admin/        # Admin dashboard
│           │   ├── cart/         # Shopping cart
│           │   ├── checkout/     # Checkout process
│           │   ├── home/         # Home page
│           │   ├── orders/       # Order history
│           │   └── shop/         # Product catalog
│           ├── layout/           # Layout components
│           └── shared/           # Shared components
│
└── docker-compose.yml            # Docker services configuration
```

## 🔑 API Endpoints

### Products
- `GET /api/products` - Get all products with filtering and pagination
- `GET /api/products/{id}` - Get product by ID
- `GET /api/products/brands` - Get all brands
- `GET /api/products/types` - Get all product types
- `POST /api/products` - Create product (Admin only)
- `PUT /api/products/{id}` - Update product (Admin only)
- `DELETE /api/products/{id}` - Delete product (Admin only)

### Cart
- `GET /api/cart` - Get shopping cart
- `POST /api/cart` - Create or update cart
- `DELETE /api/cart/{id}` - Delete cart

### Orders
- `GET /api/orders` - Get user orders
- `GET /api/orders/{id}` - Get order by ID
- `POST /api/orders` - Create order

### Payments
- `POST /api/payments/{cartId}` - Create or update payment intent
- `POST /api/payments/webhook` - Stripe webhook endpoint

### Coupons
- `GET /api/coupons/{code}` - Get coupon by code

### Account
- `POST /api/login` - User login
- `POST /api/register` - User registration
- `GET /api/account/user-info` - Get user information
- `GET /api/account/address` - Get user address
- `POST /api/account/address` - Save user address

## 🔐 Authentication

The application uses ASP.NET Core Identity with JWT tokens for authentication:
- Users can register and login
- Protected routes require authentication
- Admin routes require Admin role
- Angular guards protect client-side routes

## 💾 Database Schema

Key entities:
- **Product**: Product catalog items
- **AppUser**: User accounts
- **Address**: User shipping addresses
- **Order**: Order aggregate root
- **OrderItem**: Order line items
- **DeliveryMethod**: Shipping options
- **AppCoupon**: Discount coupons
- **ShoppingCart**: Shopping cart (stored in Redis)

## 🧪 Testing

Run backend tests:
```bash
dotnet test
```

Run frontend tests:
```bash
cd client
npm test
```

## 🐛 Error Handling

The application includes comprehensive error handling:
- Custom exception middleware
- Standardized API error responses
- Client-side error interceptors
- Error logging
- User-friendly error pages

## 📱 Real-time Features

SignalR is used for real-time notifications:
- Order status updates
- Payment confirmations
- Admin notifications
- Connected at `/hub/notifications`

## 🎨 Styling

The frontend uses:
- **Tailwind CSS**: Utility-first styling
- **Angular Material**: Pre-built components
- **Responsive Design**: Mobile-friendly interface
- **Custom Themes**: Configurable color schemes

## 🔧 Development Tools

- **Entity Framework Core CLI**: Database migrations
- **Angular CLI**: Project scaffolding and build
- **Docker Compose**: Local development environment
- **Hot Reload**: Both backend and frontend support hot reload

## 📦 Building for Production

### Backend
```bash
dotnet publish -c Release -o ./publish
```

### Frontend
```bash
cd client
npm run build
```

The built Angular app is served by the ASP.NET Core application from the `wwwroot` folder.

## 🔒 Security Features

- Password hashing with Identity
- JWT token authentication
- HTTPS enforcement
- CORS configuration
- SQL injection prevention (parameterized queries)
- XSS protection
- CSRF protection

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 👥 Support

For issues and questions, please open an issue in the repository.

## 🙏 Acknowledgments

- Built with .NET 9.0 and Angular 21
- Stripe for payment processing
- Redis for caching
- Azure SQL Edge for development database