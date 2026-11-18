import { createFileRoute } from "@tanstack/react-router";
import { RegisterPage } from "@/pages/auth/RegisterPage";

export const Route = createFileRoute("/register")({
  head: () => ({
    meta: [
      { title: "Create account — CampusConnect" },
      {
        name: "description",
        content: "Student registration for the CampusConnect academic workspace.",
      },
    ],
  }),
  component: RegisterPage,
});
