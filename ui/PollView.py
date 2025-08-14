import discord
from ui.PollButton import PollButton
import db

class PollView(discord.ui.View):
    def __init__(self, options, question, creator_id):
        super().__init__(timeout=None)  # No timeout for polls
        self.options = options
        self.question = question
        self.creator_id = creator_id
        self.poll_id = None
        
        # Create buttons for each option (max 10)
        for i, option in enumerate(options[:10]):
            button = PollButton(label=f"{i+1}. {option[:50]}", option_index=i, emoji=f"{i+1}️⃣")
            self.add_item(button)
        
        # Add results button
        results_button = discord.ui.Button(
            label="Show Results",
            style=discord.ButtonStyle.secondary,
            emoji="📊"
        )
        results_button.callback = self.show_results
        self.add_item(results_button)

    async def show_results(self, interaction: discord.Interaction):
        if not self.poll_id:
            await interaction.response.send_message("Poll ID not found.", ephemeral=True)
            return
        
        try:
            from bson import ObjectId
            poll_data = db.dbmanager.polls_collection.find_one({"_id": ObjectId(self.poll_id)})
            
            if not poll_data:
                await interaction.response.send_message("Poll not found.", ephemeral=True)
                return
            
            # Calculate results
            embed = discord.Embed(
                title=f"📊 {poll_data['question']} - Results",
                color=discord.Color.green()
            )
            
            total_votes = sum(len(voters) for voters in poll_data['votes'].values())
            
            for i, option in enumerate(poll_data['options']):
                vote_count = len(poll_data['votes'].get(str(i), []))
                percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
                
                bar = "█" * int(percentage // 5) + "░" * (20 - int(percentage // 5))
                
                embed.add_field(
                    name=f"{i+1}️⃣ {option}",
                    value=f"{bar} {vote_count} votes ({percentage:.1f}%)",
                    inline=False
                )
            
            embed.set_footer(text=f"Total votes: {total_votes}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            
        except Exception as e:
            await interaction.response.send_message(f"Error showing results: {e}", ephemeral=True)
