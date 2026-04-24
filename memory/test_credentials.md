# Scormify Test Credentials

## Super Admin
- **Email**: admin@scormify.com
- **Password**: admin123
- **Role**: super_admin

## Aprovador (Test User)
- **Email**: aprovador@teste.com
- **Password**: aprovador123
- **Role**: aprovador
- **Company**: company_didaxis001

## Company Admin - Empresa Teste RBAC (isolation test)
- **Email**: admin@empresateste.com
- **Password**: empresa123
- **Role**: company_admin
- **Company**: company_d9dec773d063
- **Usage**: validates that a company_admin from another company CANNOT see Didaxis projects (expects 0 projects visible, 404 on cross-company fetch).
