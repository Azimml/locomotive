import {
  Controller,
  Get,
  Post,
  Delete,
  Body,
  Param,
  Query,
  UseGuards,
  ParseUUIDPipe,
} from "@nestjs/common";
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiQuery,
} from "@nestjs/swagger";
import { ChatService } from "./chat.service";
import { SendMessageDto, CreateSessionDto } from "./dto/chat.dto";
import { JwtAuthGuard } from "../auth/guards/jwt-auth.guard";
import { CurrentUser } from "../auth/decorators/current-user.decorator";
import { User } from "../users/entities/user.entity";

@ApiTags("chat")
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller("api/chat")
export class ChatController {
  constructor(private readonly chatService: ChatService) {}

  @Post("sessions")
  @ApiOperation({ summary: "Yangi chat session yaratish" })
  @ApiResponse({ status: 201, description: "Session yaratildi" })
  async createSession(
    @CurrentUser() user: User,
    @Body() dto: CreateSessionDto,
  ) {
    return this.chatService.createSession(user.id, dto);
  }

  @Get("sessions")
  @ApiOperation({ summary: "Foydalanuvchi sessionlarini olish" })
  @ApiResponse({ status: 200, description: "Sessionlar ro'yxati" })
  async getUserSessions(@CurrentUser() user: User) {
    return this.chatService.getUserSessions(user.id);
  }

  @Get("sessions/:sessionId")
  @ApiOperation({ summary: "Session ma'lumotlarini olish" })
  @ApiResponse({ status: 200, description: "Session ma'lumotlari" })
  async getSession(
    @CurrentUser() user: User,
    @Param("sessionId", ParseUUIDPipe) sessionId: string,
  ) {
    return this.chatService.getSessionById(sessionId, user.id);
  }

  @Get("sessions/:sessionId/messages")
  @ApiOperation({ summary: "Session xabarlarini olish" })
  @ApiResponse({ status: 200, description: "Xabarlar ro'yxati" })
  @ApiQuery({ name: "limit", required: false, type: Number })
  @ApiQuery({ name: "offset", required: false, type: Number })
  async getSessionMessages(
    @CurrentUser() user: User,
    @Param("sessionId", ParseUUIDPipe) sessionId: string,
    @Query("limit") limit?: number,
    @Query("offset") offset?: number,
  ) {
    return this.chatService.getSessionMessages(
      sessionId,
      user.id,
      limit || 50,
      offset || 0,
    );
  }

  @Post("send")
  @ApiOperation({ summary: "Xabar yuborish" })
  @ApiResponse({ status: 201, description: "Javob qaytarildi" })
  async sendMessage(@CurrentUser() user: User, @Body() dto: SendMessageDto) {
    return this.chatService.sendMessage(user.id, dto);
  }

  @Delete("sessions/:sessionId")
  @ApiOperation({ summary: "Sessionni o'chirish" })
  @ApiResponse({ status: 200, description: "Session o'chirildi" })
  async deleteSession(
    @CurrentUser() user: User,
    @Param("sessionId", ParseUUIDPipe) sessionId: string,
  ) {
    await this.chatService.deleteSession(sessionId, user.id);
    return { success: true };
  }
}
