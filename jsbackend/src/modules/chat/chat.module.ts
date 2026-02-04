import { Module } from "@nestjs/common";
import { TypeOrmModule } from "@nestjs/typeorm";
import { ChatSession } from "./entities/chat-session.entity";
import { Message } from "./entities/message.entity";
import { ChatService } from "./chat.service";
import { ChatController } from "./chat.controller";
import { AiModule } from "../ai/ai.module";

@Module({
  imports: [TypeOrmModule.forFeature([ChatSession, Message]), AiModule],
  controllers: [ChatController],
  providers: [ChatService],
  exports: [ChatService],
})
export class ChatModule {}
