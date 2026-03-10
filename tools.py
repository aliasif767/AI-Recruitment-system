import os
from github import Github


class GithubAuditTool:
    name = "github_audit_tool"
    description = "Fetches GitHub repositories, languages, stars, and profile summary."

    def _run(self, github_username: str) -> str:
        if not github_username or github_username.lower() in ["unknown", "not_found", "none", ""]:
            return "No GitHub handle provided."

        token = os.getenv("GITHUB_TOKEN")
        g = Github(token) if token else Github()

        try:
            user = g.get_user(github_username)
            repos = list(user.get_repos())[:10]

            language_count = {}
            repo_summaries = []
            total_stars = 0
            total_forks = 0

            for repo in repos:
                lang = repo.language or "Unknown"
                language_count[lang] = language_count.get(lang, 0) + 1
                total_stars += repo.stargazers_count
                total_forks += repo.forks_count
                topics = ", ".join(repo.get_topics()[:4]) if repo.get_topics() else "none"
                repo_summaries.append(
                    f"REPO: {repo.name} | LANG: {lang} | STARS: {repo.stargazers_count} "
                    f"| FORKS: {repo.forks_count} | TOPICS: {topics} "
                    f"| DESC: {repo.description or 'No description'}"
                )

            top_langs = sorted(language_count.items(), key=lambda x: x[1], reverse=True)
            lang_str = ", ".join([f"{l}({c} repos)" for l, c in top_langs[:6]])

            profile_info = (
                f"GITHUB_PROFILE\n"
                f"Username: {user.login}\n"
                f"Name: {user.name or 'N/A'}\n"
                f"Bio: {user.bio or 'N/A'}\n"
                f"Company: {user.company or 'N/A'}\n"
                f"Location: {user.location or 'N/A'}\n"
                f"Public Repos: {user.public_repos}\n"
                f"Followers: {user.followers}\n"
                f"Total Stars: {total_stars}\n"
                f"Total Forks: {total_forks}\n"
                f"Top Languages: {lang_str}\n\n"
                f"TOP REPOSITORIES:\n" + "\n".join(repo_summaries)
            )
            return profile_info

        except Exception as e:
            return f"GitHub fetch failed for '{github_username}': {str(e)}"