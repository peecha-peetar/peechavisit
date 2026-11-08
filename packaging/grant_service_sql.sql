-- grant_service_sql.sql - پیچا ویزیت | دسترسی سرویس ویندوز به SQL Server
-- ════════════════════════════════════════════════
-- فقط وقتی لازم است که اتصال دیتابیس «ورود ویندوزی» باشد (نام کاربری SQL خالی).
-- سرویس با حساب SYSTEM اجرا می‌شود؛ این اسکریپت را یک بار در SQL Server
-- Management Studio (روی همان سرور) اجرا کنید.
-- اگر نام دیتابیس‌ها فرق دارد، tracking و dejavuDB1 را عوض کنید.
-- ════════════════════════════════════════════════
USE master;
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'NT AUTHORITY\SYSTEM')
    CREATE LOGIN [NT AUTHORITY\SYSTEM] FROM WINDOWS;
GO

-- دیتابیس پیچا ویزیت: خواندن، نوشتن و ساخت جدول‌ها
USE tracking;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'NT AUTHORITY\SYSTEM')
    CREATE USER [NT AUTHORITY\SYSTEM] FOR LOGIN [NT AUTHORITY\SYSTEM];
ALTER ROLE db_owner ADD MEMBER [NT AUTHORITY\SYSTEM];
GO

-- دیتابیس فروش (مشتری و کالا): فقط خواندن
USE dejavuDB1;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'NT AUTHORITY\SYSTEM')
    CREATE USER [NT AUTHORITY\SYSTEM] FOR LOGIN [NT AUTHORITY\SYSTEM];
ALTER ROLE db_datareader ADD MEMBER [NT AUTHORITY\SYSTEM];
GO
