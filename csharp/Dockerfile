FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY global.json Banking.sln ./
COPY csharp/Directory.Build.props csharp/
COPY csharp/Banking.Domain/Banking.Domain.csproj csharp/Banking.Domain/packages.lock.json csharp/Banking.Domain/
COPY csharp/Banking.Application/Banking.Application.csproj csharp/Banking.Application/packages.lock.json csharp/Banking.Application/
COPY csharp/Banking.Infrastructure/Banking.Infrastructure.csproj csharp/Banking.Infrastructure/packages.lock.json csharp/Banking.Infrastructure/
COPY csharp/Banking.Tests/Banking.Tests.csproj csharp/Banking.Tests/packages.lock.json csharp/Banking.Tests/
COPY csharp/Banking.Api/Banking.Api.csproj csharp/Banking.Api/packages.lock.json csharp/Banking.Api/
COPY csharp/Banking.Audit/Banking.Audit.csproj csharp/Banking.Audit/packages.lock.json csharp/Banking.Audit/
RUN dotnet restore Banking.sln --locked-mode
COPY csharp/ csharp/
RUN dotnet test Banking.sln --no-restore -c Release
RUN dotnet publish csharp/Banking.Api -c Release --no-restore -o /api
RUN dotnet publish csharp/Banking.Audit -c Release --no-restore -o /audit

FROM mcr.microsoft.com/dotnet/aspnet:10.0@sha256:57460add89e2b3dd1950c41d8b7dc96eeb7a24d13d98e3656ce9997a8b746bd6 AS runtime-base
RUN apt-get update && apt-get install -y --no-install-recommends libssl3t64 openssl libgssapi-krb5-2 && rm -rf /var/lib/apt/lists/*

FROM runtime-base AS api
WORKDIR /app
COPY --from=build /api .
USER $APP_UID
EXPOSE 8080
ENTRYPOINT ["dotnet", "Banking.Api.dll"]

FROM runtime-base AS audit
WORKDIR /app
COPY --from=build /audit .
USER $APP_UID
ENTRYPOINT ["dotnet", "Banking.Audit.dll"]
