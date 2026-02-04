import { Injectable, NotFoundException, Logger } from "@nestjs/common";
import { InjectRepository } from "@nestjs/typeorm";
import { Repository } from "typeorm";
import { ChatSession } from "./entities/chat-session.entity";
import { Message, MessageRole } from "./entities/message.entity";
import { AiService } from "../ai/ai.service";
import { SendMessageDto, CreateSessionDto } from "./dto/chat.dto";

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);

  constructor(
    @InjectRepository(ChatSession)
    private readonly sessionRepository: Repository<ChatSession>,
    @InjectRepository(Message)
    private readonly messageRepository: Repository<Message>,
    private readonly aiService: AiService,
  ) {}

  async createSession(
    userId: string,
    dto?: CreateSessionDto,
  ): Promise<ChatSession> {
    const session = this.sessionRepository.create({
      userId,
      title: dto?.title || "Yangi suhbat",
    });
    return this.sessionRepository.save(session);
  }

  async getUserSessions(userId: string): Promise<ChatSession[]> {
    return this.sessionRepository.find({
      where: { userId, isActive: true },
      order: { updatedAt: "DESC" },
      select: ["id", "title", "createdAt", "updatedAt"],
    });
  }

  async getSessionById(
    sessionId: string,
    userId: string,
  ): Promise<ChatSession> {
    const session = await this.sessionRepository.findOne({
      where: { id: sessionId, userId },
    });

    if (!session) {
      throw new NotFoundException("Session topilmadi");
    }

    return session;
  }

  async getSessionMessages(
    sessionId: string,
    userId: string,
    limit = 50,
    offset = 0,
  ): Promise<Message[]> {
    await this.getSessionById(sessionId, userId);

    return this.messageRepository.find({
      where: { sessionId },
      order: { createdAt: "ASC" },
      take: limit,
      skip: offset,
    });
  }

  async sendMessage(
    userId: string,
    dto: SendMessageDto,
  ): Promise<{ session: ChatSession; response: Message }> {
    let session: ChatSession;

    if (dto.sessionId) {
      session = await this.getSessionById(dto.sessionId, userId);
    } else {
      session = await this.createSession(userId, {
        title: this.generateSessionTitle(dto.message),
      });
    }

    const userMessage = await this.saveMessage(
      session.id,
      MessageRole.USER,
      dto.message,
    );

    const conversationHistory = await this.getConversationHistory(session.id);

    this.logger.log(`Processing message: "${dto.message}"`);
    this.logger.log(
      `Conversation history length: ${conversationHistory.length}`,
    );

    try {
      const aiResponse = await this.aiService.processMessage(
        dto.message,
        conversationHistory,
      );

      this.logger.log(
        `AI Response received: ${aiResponse.content?.slice(0, 100)}...`,
      );
      this.logger.log(
        `Tools used: ${aiResponse.metadata?.toolsUsed?.join(", ") || "none"}`,
      );

      const assistantMessage = await this.saveMessage(
        session.id,
        MessageRole.ASSISTANT,
        aiResponse.content,
        aiResponse.metadata,
      );

      await this.sessionRepository.update(session.id, {
        updatedAt: new Date(),
      });

      return {
        session,
        response: assistantMessage,
      };
    } catch (error) {
      this.logger.error("Error processing message:", error);
      throw error;
    }
  }

  async deleteSession(sessionId: string, userId: string): Promise<void> {
    const session = await this.getSessionById(sessionId, userId);
    await this.sessionRepository.update(session.id, { isActive: false });
  }

  private async saveMessage(
    sessionId: string,
    role: MessageRole,
    content: string,
    metadata?: Record<string, any>,
  ): Promise<Message> {
    const message = this.messageRepository.create({
      sessionId,
      role,
      content,
      metadata,
    });
    return this.messageRepository.save(message);
  }

  private async getConversationHistory(
    sessionId: string,
    limit = 20,
  ): Promise<Array<{ role: string; content: string }>> {
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

  private generateSessionTitle(message: string): string {
    const maxLength = 50;
    if (message.length <= maxLength) {
      return message;
    }
    return message.substring(0, maxLength) + "...";
  }
}
