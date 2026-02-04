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
exports.Message = exports.MessageRole = void 0;
const typeorm_1 = require("typeorm");
const chat_session_entity_1 = require("./chat-session.entity");
var MessageRole;
(function (MessageRole) {
    MessageRole["USER"] = "user";
    MessageRole["ASSISTANT"] = "assistant";
    MessageRole["SYSTEM"] = "system";
    MessageRole["TOOL"] = "tool";
})(MessageRole || (exports.MessageRole = MessageRole = {}));
let Message = class Message {
};
exports.Message = Message;
__decorate([
    (0, typeorm_1.PrimaryGeneratedColumn)("uuid"),
    __metadata("design:type", String)
], Message.prototype, "id", void 0);
__decorate([
    (0, typeorm_1.Index)(),
    (0, typeorm_1.Column)({ name: "session_id" }),
    __metadata("design:type", String)
], Message.prototype, "sessionId", void 0);
__decorate([
    (0, typeorm_1.ManyToOne)(() => chat_session_entity_1.ChatSession, (session) => session.messages, {
        onDelete: "CASCADE",
    }),
    (0, typeorm_1.JoinColumn)({ name: "session_id" }),
    __metadata("design:type", chat_session_entity_1.ChatSession)
], Message.prototype, "session", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: "enum", enum: MessageRole }),
    __metadata("design:type", String)
], Message.prototype, "role", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: "text" }),
    __metadata("design:type", String)
], Message.prototype, "content", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: "jsonb", nullable: true }),
    __metadata("design:type", Object)
], Message.prototype, "metadata", void 0);
__decorate([
    (0, typeorm_1.Column)({ type: "jsonb", nullable: true }),
    __metadata("design:type", Array)
], Message.prototype, "toolCalls", void 0);
__decorate([
    (0, typeorm_1.Column)({ nullable: true }),
    __metadata("design:type", String)
], Message.prototype, "toolCallId", void 0);
__decorate([
    (0, typeorm_1.CreateDateColumn)(),
    __metadata("design:type", Date)
], Message.prototype, "createdAt", void 0);
exports.Message = Message = __decorate([
    (0, typeorm_1.Entity)("messages"),
    (0, typeorm_1.Index)(["sessionId", "createdAt"])
], Message);
//# sourceMappingURL=message.entity.js.map