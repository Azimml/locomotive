"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppModule = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const typeorm_1 = require("@nestjs/typeorm");
const seed_service_1 = require("./database/seeds/seed.service");
const database_config_1 = require("./config/database.config");
const auth_1 = require("./modules/auth");
const users_1 = require("./modules/users");
const chat_1 = require("./modules/chat");
const ai_1 = require("./modules/ai");
const locomotive_1 = require("./modules/locomotive");
let AppModule = class AppModule {
    constructor(seedService) {
        this.seedService = seedService;
    }
    async onModuleInit() {
        await this.seedService.seed();
    }
};
exports.AppModule = AppModule;
exports.AppModule = AppModule = __decorate([
    (0, common_1.Module)({
        imports: [
            config_1.ConfigModule.forRoot({
                isGlobal: true,
                envFilePath: ".env",
            }),
            typeorm_1.TypeOrmModule.forRootAsync({
                imports: [config_1.ConfigModule],
                useFactory: database_config_1.getDatabaseConfig,
                inject: [config_1.ConfigService],
            }),
            auth_1.AuthModule,
            users_1.UsersModule,
            chat_1.ChatModule,
            ai_1.AiModule,
            locomotive_1.LocomotiveModule,
        ],
        providers: [seed_service_1.SeedService],
    }),
    __metadata("design:paramtypes", [seed_service_1.SeedService])
], AppModule);
//# sourceMappingURL=app.module.js.map