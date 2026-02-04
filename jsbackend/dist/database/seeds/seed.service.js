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
var SeedService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.SeedService = void 0;
const users_1 = require("../../modules/users");
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
let SeedService = SeedService_1 = class SeedService {
    constructor(usersService, configService) {
        this.usersService = usersService;
        this.configService = configService;
        this.logger = new common_1.Logger(SeedService_1.name);
    }
    async seed() {
        await this.seedDefaultUser();
    }
    async seedDefaultUser() {
        const defaultLogin = this.configService.get("DEFAULT_ADMIN_LOGIN");
        const defaultPassword = this.configService.get("DEFAULT_ADMIN_PASSWORD");
        if (!defaultLogin || !defaultPassword) {
            this.logger.warn("Default admin credentials not configured");
            return;
        }
        const exists = await this.usersService.exists(defaultLogin);
        if (!exists) {
            await this.usersService.create(defaultLogin, defaultPassword, "Administrator");
            this.logger.log(`Default admin user created: ${defaultLogin}`);
        }
        else {
            this.logger.log("Default admin user already exists");
        }
    }
};
exports.SeedService = SeedService;
exports.SeedService = SeedService = SeedService_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [users_1.UsersService,
        config_1.ConfigService])
], SeedService);
//# sourceMappingURL=seed.service.js.map