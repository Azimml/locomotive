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
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ChatController = void 0;
const common_1 = require("@nestjs/common");
const swagger_1 = require("@nestjs/swagger");
const chat_service_1 = require("./chat.service");
const chat_dto_1 = require("./dto/chat.dto");
const jwt_auth_guard_1 = require("../auth/guards/jwt-auth.guard");
const current_user_decorator_1 = require("../auth/decorators/current-user.decorator");
const user_entity_1 = require("../users/entities/user.entity");
let ChatController = class ChatController {
    constructor(chatService) {
        this.chatService = chatService;
    }
    async createSession(user, dto) {
        return this.chatService.createSession(user.id, dto);
    }
    async getUserSessions(user) {
        return this.chatService.getUserSessions(user.id);
    }
    async getSession(user, sessionId) {
        return this.chatService.getSessionById(sessionId, user.id);
    }
    async getSessionMessages(user, sessionId, limit, offset) {
        return this.chatService.getSessionMessages(sessionId, user.id, limit || 50, offset || 0);
    }
    async sendMessage(user, dto) {
        return this.chatService.sendMessage(user.id, dto);
    }
    async deleteSession(user, sessionId) {
        await this.chatService.deleteSession(sessionId, user.id);
        return { success: true };
    }
};
exports.ChatController = ChatController;
__decorate([
    (0, common_1.Post)("sessions"),
    (0, swagger_1.ApiOperation)({ summary: "Yangi chat session yaratish" }),
    (0, swagger_1.ApiResponse)({ status: 201, description: "Session yaratildi" }),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [user_entity_1.User,
        chat_dto_1.CreateSessionDto]),
    __metadata("design:returntype", Promise)
], ChatController.prototype, "createSession", null);
__decorate([
    (0, common_1.Get)("sessions"),
    (0, swagger_1.ApiOperation)({ summary: "Foydalanuvchi sessionlarini olish" }),
    (0, swagger_1.ApiResponse)({ status: 200, description: "Sessionlar ro'yxati" }),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [user_entity_1.User]),
    __metadata("design:returntype", Promise)
], ChatController.prototype, "getUserSessions", null);
__decorate([
    (0, common_1.Get)("sessions/:sessionId"),
    (0, swagger_1.ApiOperation)({ summary: "Session ma'lumotlarini olish" }),
    (0, swagger_1.ApiResponse)({ status: 200, description: "Session ma'lumotlari" }),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __param(1, (0, common_1.Param)("sessionId", common_1.ParseUUIDPipe)),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [user_entity_1.User, String]),
    __metadata("design:returntype", Promise)
], ChatController.prototype, "getSession", null);
__decorate([
    (0, common_1.Get)("sessions/:sessionId/messages"),
    (0, swagger_1.ApiOperation)({ summary: "Session xabarlarini olish" }),
    (0, swagger_1.ApiResponse)({ status: 200, description: "Xabarlar ro'yxati" }),
    (0, swagger_1.ApiQuery)({ name: "limit", required: false, type: Number }),
    (0, swagger_1.ApiQuery)({ name: "offset", required: false, type: Number }),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __param(1, (0, common_1.Param)("sessionId", common_1.ParseUUIDPipe)),
    __param(2, (0, common_1.Query)("limit")),
    __param(3, (0, common_1.Query)("offset")),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [user_entity_1.User, String, Number, Number]),
    __metadata("design:returntype", Promise)
], ChatController.prototype, "getSessionMessages", null);
__decorate([
    (0, common_1.Post)("send"),
    (0, swagger_1.ApiOperation)({ summary: "Xabar yuborish" }),
    (0, swagger_1.ApiResponse)({ status: 201, description: "Javob qaytarildi" }),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [user_entity_1.User, chat_dto_1.SendMessageDto]),
    __metadata("design:returntype", Promise)
], ChatController.prototype, "sendMessage", null);
__decorate([
    (0, common_1.Delete)("sessions/:sessionId"),
    (0, swagger_1.ApiOperation)({ summary: "Sessionni o'chirish" }),
    (0, swagger_1.ApiResponse)({ status: 200, description: "Session o'chirildi" }),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __param(1, (0, common_1.Param)("sessionId", common_1.ParseUUIDPipe)),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [user_entity_1.User, String]),
    __metadata("design:returntype", Promise)
], ChatController.prototype, "deleteSession", null);
exports.ChatController = ChatController = __decorate([
    (0, swagger_1.ApiTags)("chat"),
    (0, swagger_1.ApiBearerAuth)(),
    (0, common_1.UseGuards)(jwt_auth_guard_1.JwtAuthGuard),
    (0, common_1.Controller)("api/chat"),
    __metadata("design:paramtypes", [chat_service_1.ChatService])
], ChatController);
//# sourceMappingURL=chat.controller.js.map