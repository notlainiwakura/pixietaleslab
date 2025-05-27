import React from 'react';
import { CssBaseline, Container, Box, Typography } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import theme from './theme';
// import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import BookFormWizard from './BookFormWizard';
// import BookPreview from './BookPreview';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ bgcolor: 'background.default', minHeight: '100vh', py: 4 }}>
        <Container maxWidth="md">
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <Typography variant="h2" fontWeight={700} color="secondary" gutterBottom>
              Welcome to PixieTales Lab
            </Typography>
            <Typography variant="h5" color="text.secondary">
              Let's create your own coloring book!
            </Typography>
          </Box>
          <BookFormWizard />
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;
