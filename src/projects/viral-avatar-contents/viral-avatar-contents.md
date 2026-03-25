# Viral Avatar Contents

> Project ID: `b70b611497d141b48ab90c6a9bb9ecb9`

> Last updated: 2026-03-23 14:28 UTC

## Configuration

- **Confluence Space**: CrewAITS
- **Jira Project**: CVAC
- **Figma Team ID**: 1554879494572350747

## Idea-Iteration Guardrails

- create a crewai agents that generate a personal video avatar with user voice over that can take a single content to provide a 15-60 seconds videos segment to be publish in media like tiktok and facebook. Make suggestion of tools to use to generate avatar, generate voice, generate scripted content from an idea, generate video combining all avatar, voice, and scripted content.
- User Features:
- 1. Allow user to create an account in with gmail or email account.
- 2. Allow user to create multiple media channels. Each channel consist of list of social media like tiktok, youtube shorts, threads, and X but not limited to it.
- 3. Allow user personalize an avatar per media channel.
- 4. Allow user to generate a content from a simple idea and iterate through it.
- 5. System generate multiple media results for user to finalize and use it to publish into a medial channel.
- Personalilzing an Avatar:
- 1. Upload 5-10 pictures of a person to model the avatar.
- 2. Upload voice of the avatar to be use as voice over in given content script.
- Requirements:
- Use the latest AI models, low cost to free, and specific to the neeed like (avatar, voice, script, image, and video).
- Seperate out the data layer with API and webhook between Web/Mobile/Slack
- Minimal Viable Product:
- Able to generate an avatar content using slack before creating a full fledge website.

## Knowledge References

- [note] <https://docs.crewai.com/en/concepts/agents>
- [note] <https://docs.crewai.com/en/concepts/tasks>
- [note] <https://docs.crewai.com/en/concepts/crews>
- [note] <https://docs.crewai.com/en/concepts/flows>
- [note] <https://docs.crewai.com/en/concepts/production-architecture>
- [note] <https://docs.crewai.com/en/concepts/knowledge>
- [note] <https://docs.crewai.com/en/concepts/collaboration>
- [note] <https://docs.crewai.com/en/concepts/training>
- [note] <https://docs.crewai.com/en/concepts/memory>
- [note] <https://docs.crewai.com/en/concepts/reasoning>
- [note] <https://docs.crewai.com/en/concepts/event-listener>

## Technology Stack

- _MongoDB Atlas for persistence_
- _FastAPI for REST and Webhook endpoints_
- _React + TypeScript for frontend_
- _RabbitMQ pub/sub_
- _Event listener using CrewAI framework event listener_ <https://docs.crewai.com/en/concepts/event-listener>
- CrewAI framework for Agents and product flow
- Obsedian for LLM knowledge
- Gemini for for agent LLM
- Clip + ViT for Vision recognition of image and video
- Voice with ElevenLabs
- Video gen with HeyGen
- Reference video download with yt-dlp

## Completed Ideas

- [[ideas/a-platform-that-takes-a-creative-idea-and-converts-it-into-a-30-90-second-or.md|A Platform That Takes A Creative Idea And Converts It Into A 30 90 Second Or]]
