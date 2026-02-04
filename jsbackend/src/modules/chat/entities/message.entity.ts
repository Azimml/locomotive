import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  Index,
  JoinColumn,
} from "typeorm";
import { ChatSession } from "./chat-session.entity";

export enum MessageRole {
  USER = "user",
  ASSISTANT = "assistant",
  SYSTEM = "system",
  TOOL = "tool",
}

@Entity("messages")
@Index(["sessionId", "createdAt"])
export class Message {
  @PrimaryGeneratedColumn("uuid")
  id: string;

  @Index()
  @Column({ name: "session_id" })
  sessionId: string;

  @ManyToOne(() => ChatSession, (session) => session.messages, {
    onDelete: "CASCADE",
  })
  @JoinColumn({ name: "session_id" })
  session: ChatSession;

  @Column({ type: "enum", enum: MessageRole })
  role: MessageRole;

  @Column({ type: "text" })
  content: string;

  @Column({ type: "jsonb", nullable: true })
  metadata: Record<string, any>;

  @Column({ type: "jsonb", nullable: true })
  toolCalls: any[];

  @Column({ nullable: true })
  toolCallId: string;

  @CreateDateColumn()
  createdAt: Date;
}
