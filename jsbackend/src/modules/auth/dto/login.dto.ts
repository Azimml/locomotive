import { IsString, MinLength, MaxLength } from "class-validator";
import { ApiProperty } from "@nestjs/swagger";

export class LoginDto {
  @ApiProperty({ example: "admin" })
  @IsString()
  @MinLength(3)
  @MaxLength(50)
  login: string;

  @ApiProperty({ example: "admin123" })
  @IsString()
  @MinLength(6)
  @MaxLength(100)
  password: string;
}
