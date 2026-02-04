"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getDatabaseConfig = void 0;
const getDatabaseConfig = (configService) => ({
    type: "postgres",
    host: configService.get("DB_HOST"),
    port: configService.get("DB_PORT"),
    username: configService.get("DB_USERNAME"),
    password: configService.get("DB_PASSWORD"),
    database: configService.get("DB_NAME"),
    entities: [__dirname + "/../**/*.entity{.ts,.js}"],
    synchronize: true,
    logging: configService.get("NODE_ENV") === "development",
    poolSize: 20,
    extra: {
        max: 20,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000,
    },
});
exports.getDatabaseConfig = getDatabaseConfig;
//# sourceMappingURL=database.config.js.map