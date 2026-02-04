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
var ChatService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.ChatService = void 0;
const common_1 = require("@nestjs/common");
const typeorm_1 = require("@nestjs/typeorm");
const typeorm_2 = require("typeorm");
const chat_session_entity_1 = require("./entities/chat-session.entity");
const message_entity_1 = require("./entities/message.entity");
const ai_service_1 = require("../ai/ai.service");
let ChatService = ChatService_1 = class ChatService {
    constructor(sessionRepository, messageRepository, aiService) {
        this.sessionRepository = sessionRepository;
        this.messageRepository = messageRepository;
        this.aiService = aiService;
        this.logger = new common_1.Logger(ChatService_1.name);
    }
    async createSession(userId, dto) {
        const session = this.sessionRepository.create({
            userId,
            title: dto?.title || "Yangi suhbat",
        });
        return this.sessionRepository.save(session);
    }
    async getUserSessions(userId) {
        return this.sessionRepository.find({
            where: { userId, isActive: true },
            order: { updatedAt: "DESC" },
            select: ["id", "title", "createdAt", "updatedAt"],
        });
    }
    async getSessionById(sessionId, userId) {
        const session = await this.sessionRepository.findOne({
            where: { id: sessionId, userId },
        });
        if (!session) {
            throw new common_1.NotFoundException("Session topilmadi");
        }
        return session;
    }
    async getSessionMessages(sessionId, userId, limit = 50, offset = 0) {
        await this.getSessionById(sessionId, userId);
        return this.messageRepository.find({
            where: { sessionId },
            order: { createdAt: "ASC" },
            take: limit,
            skip: offset,
        });
    }
    async sendMessage(userId, dto) {
        let session;
        if (dto.sessionId) {
            session = await this.getSessionById(dto.sessionId, userId);
        }
        else {
            session = await this.createSession(userId, {
                title: this.generateSessionTitle(dto.message),
            });
        }
        const userMessage = await this.saveMessage(session.id, message_entity_1.MessageRole.USER, dto.message);
        const conversationHistory = await this.getConversationHistory(session.id);
        this.logger.log(`Processing message: "${dto.message}"`);
        this.logger.log(`Conversation history length: ${conversationHistory.length}`);
        try {
            const aiResponse = await this.aiService.processMessage(dto.message, conversationHistory);
            this.logger.log(`AI Response received: ${aiResponse.content?.slice(0, 100)}...`);
            this.logger.log(`Tools used: ${aiResponse.metadata?.toolsUsed?.join(", ") || "none"}`);
            const assistantMessage = await this.saveMessage(session.id, message_entity_1.MessageRole.ASSISTANT, aiResponse.content, aiResponse.metadata);
            await this.sessionRepository.update(session.id, {
                updatedAt: new Date(),
            });
            return {
                session,
                response: assistantMessage,
            };
        }
        catch (error) {
            this.logger.error("Error processing message:", error);
            throw error;
        }
    }
    async deleteSession(sessionId, userId) {
        const session = await this.getSessionById(sessionId, userId);
        await this.sessionRepository.update(session.id, { isActive: false });
    }
    async saveMessage(sessionId, role, content, metadata) {
        const message = this.messageRepository.create({
            sessionId,
            role,
            content,
            metadata,
        });
        return this.messageRepository.save(message);
    }
    async getConversationHistory(sessionId, limit = 20) {
        const messages = await this.messageRepository.find({
            where: { sessionId },
            order: { createdAt: "DESC" },
            take: limit,
            select: ["role", "content"],
        });
        return messages.reverse().map((m) => ({
            role: m.role,
            content: m.content,
        }));
    }
    generateSessionTitle(message) {
        const maxLength = 50;
        if (message.length <= maxLength) {
            return message;
        }
        return message.substring(0, maxLength) + "...";
    }
};
exports.ChatService = ChatService;
exports.ChatService = ChatService = ChatService_1 = __decorate([
    (0, common_1.Injectable)(),
    __param(0, (0, typeorm_1.InjectRepository)(chat_session_entity_1.ChatSession)),
    __param(1, (0, typeorm_1.InjectRepository)(message_entity_1.Message)),
    __metadata("design:paramtypes", [typeorm_2.Repository,
        typeorm_2.Repository,
        ai_service_1.AiService])
], ChatService);
//# sourceMappingURL=chat.service.js.map