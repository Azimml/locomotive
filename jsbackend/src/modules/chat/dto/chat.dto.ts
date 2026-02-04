import { IsString, IsOptional, IsUUID, MaxLength } from "class-validator";
import { ApiProperty, ApiPropertyOptional } from "@nestjs/swagger";

export class SendMessageDto {
  @ApiProperty({ description: "Foydalanuvchi xabari" })
  @IsString()
  @MaxLength(10000)
  message: string;

  @ApiPropertyOptional({ description: "Chat session ID" })
  @IsOptional()
  @IsUUID()
  sessionId?: string;
}

export class CreateSessionDto {
  @ApiPropertyOptional({ description: "Session nomi" })
  @IsOptional()
  @IsString()
  @MaxLength(255)
  title?: string;
}
