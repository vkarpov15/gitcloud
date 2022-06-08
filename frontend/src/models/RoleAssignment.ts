import { User } from ".";

export type RoleAssignmentParams = { userId: string; role: string };

export class RoleAssignment {
  user: User;
  role: string;

  constructor({ user, role }: RoleAssignment) {
    this.user = new User(user);
    this.role = role;
  }
}
