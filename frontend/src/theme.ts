import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    primary: {
      main: '#D6EAF8', // gentle blue
      contrastText: '#3a3a3a',
    },
    secondary: {
      main: '#FADADD', // gentle pink
      contrastText: '#3a3a3a',
    },
    background: {
      default: '#FDF6F0', // gentle beige
      paper: '#FFFFFF',
    },
    text: {
      primary: '#3a3a3a',
      secondary: '#6d6d6d',
    },
  },
  typography: {
    fontFamily: '"Quicksand", "Comic Sans MS", "Arial Rounded MT Bold", Arial, sans-serif',
    h2: {
      fontWeight: 700,
    },
    h5: {
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 16,
  },
});

export default theme; 